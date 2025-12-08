import os
import re
import time
import asyncio
import logging
import aiohttp
from typing import Optional, Tuple
from pyrogram import Client
from pyrogram.types import Message
from config import (
    DOWNLOAD_LOCATION, 
    PIXELDRAIN_USE_PROXY,
    PIXELDRAIN_PROXY_LIST,
    PIXELDRAIN_AUTO_PROXY,
    PIXELDRAIN_ARIA2C_CONNECTIONS,
    TG_MAX_FILE_SIZE
)
from functions.aria2c_helper import build_aria2c_command, run_aria2c
from functions.proxy_manager import ProxyManager
from functions.progress import humanbytes, progress_for_pyrogram
from functions.ffmpeg import DocumentThumb, VideoMetaData

LOGGER = logging.getLogger(__name__)


def is_pixeldrain_url(url: str) -> bool:
    """
    URL'nin Pixeldrain linki olup olmadığını kontrol eder
    
    Note: This is a simple domain check for routing purposes only,
    not for security sanitization. The actual URL is validated
    with regex in extract_pixeldrain_id().
    
    Args:
        url: Kontrol edilecek URL
        
    Returns:
        True = Pixeldrain linki, False = değil
    """
    # Simple substring check for routing - not for security
    return "pixeldrain.com" in url.lower()


def extract_pixeldrain_id(url: str) -> Optional[str]:
    """
    Pixeldrain URL'sinden dosya ID'sini çıkarır
    
    Args:
        url: Pixeldrain URL'si
        
    Returns:
        Dosya ID'si veya None
    """
    # Örnek URL: https://pixeldrain.com/u/XXXXXXXX
    pattern = r'pixeldrain\.com/u/([a-zA-Z0-9_-]+)'
    match = re.search(pattern, url)
    if match:
        return match.group(1)
    return None


def get_direct_download_url(file_id: str) -> str:
    """
    Pixeldrain dosya ID'sinden direkt indirme URL'si oluşturur
    
    Args:
        file_id: Pixeldrain dosya ID'si
        
    Returns:
        Direkt indirme URL'si
    """
    return f"https://pixeldrain.com/api/file/{file_id}"


async def get_file_info(file_id: str) -> Optional[dict]:
    """
    Pixeldrain API'sinden dosya bilgilerini çeker
    
    Args:
        file_id: Pixeldrain dosya ID'si
        
    Returns:
        Dosya bilgileri (name, size, etc.) veya None
    """
    try:
        url = f"https://pixeldrain.com/api/file/{file_id}/info"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    data = await response.json()
                    LOGGER.info(f"Pixeldrain dosya bilgisi: {data.get('name', 'N/A')}, {data.get('size', 'N/A')} bytes")
                    return data
                else:
                    LOGGER.warning(f"Dosya bilgisi alınamadı, HTTP {response.status}")
                    return None
    except Exception as e:
        LOGGER.error(f"Dosya bilgisi alma hatası: {e}")
        return None


async def download_with_aria2c(
    url: str,
    output_path: str,
    proxy_manager: Optional[ProxyManager],
    progress_callback=None,
    max_retries: int = 3
) -> Tuple[bool, str]:
    """
    aria2c ile dosya indirir, proxy rotasyonu ile
    
    Args:
        url: İndirilecek dosya URL'si
        output_path: Çıktı dosya yolu
        proxy_manager: Proxy yönetici
        progress_callback: Progress callback fonksiyonu
        max_retries: Maksimum deneme sayısı
        
    Returns:
        (başarılı mı, hata mesajı)
    """
    for attempt in range(max_retries):
        try:
            # Proxy seç
            proxy = None
            if proxy_manager and PIXELDRAIN_USE_PROXY:
                proxy = await proxy_manager.get_next_proxy()
                if proxy:
                    LOGGER.info(f"Deneme {attempt + 1}/{max_retries}: Proxy kullanılıyor: {proxy}")
                else:
                    LOGGER.warning(f"Deneme {attempt + 1}/{max_retries}: Proxy bulunamadı, direkt bağlantı deneniyor")
            
            # User-Agent rotasyonu
            user_agent = None
            if proxy_manager:
                user_agent = proxy_manager.get_random_user_agent()
            
            # aria2c komutu oluştur
            command = build_aria2c_command(
                url=url,
                output_path=output_path,
                connections=PIXELDRAIN_ARIA2C_CONNECTIONS,
                proxy=proxy,
                user_agent=user_agent,
                referer="https://pixeldrain.com/"
            )
            
            # aria2c'yi çalıştır
            success, error = await run_aria2c(command, progress_callback)
            
            if success:
                LOGGER.info("aria2c ile indirme başarılı")
                return True, ""
            else:
                LOGGER.warning(f"aria2c hatası: {error}")
                
                # Proxy başarısızsa işaretle
                if proxy and proxy_manager:
                    proxy_manager.mark_proxy_failed(proxy)
                
                # Rate limit hatası kontrolü
                if "429" in error or "limit" in error.lower():
                    LOGGER.warning("Rate limit hatası tespit edildi, yeni proxy deneniyor")
                    await asyncio.sleep(2)
                    continue
                
                # Diğer hatalar için kısa bekleme
                if attempt < max_retries - 1:
                    await asyncio.sleep(3)
                    
        except Exception as e:
            LOGGER.error(f"aria2c indirme exception: {str(e)}")
            if attempt < max_retries - 1:
                await asyncio.sleep(3)
    
    return False, "Maksimum deneme sayısına ulaşıldı"


async def pixeldrain_download(bot: Client, message: Message, url: str):
    """
    Pixeldrain dosyasını indirir ve yükler
    
    Args:
        bot: Pyrogram Client
        message: Kullanıcı mesajı
        url: Pixeldrain URL'si (veya URL|custom_filename formatı)
    """
    # İlk mesaj
    status_msg = await message.reply_text("📥 Pixeldrain linki tespit edildi, hazırlanıyor...")
    
    try:
        # URL ve özel dosya adını ayır
        custom_filename = None
        if "|" in url:
            parts = url.split("|", 1)
            url = parts[0].strip()
            custom_filename = parts[1].strip() if len(parts) > 1 else None
        
        # Dosya ID'sini çıkar
        file_id = extract_pixeldrain_id(url)
        if not file_id:
            await status_msg.edit_text("❌ Geçersiz Pixeldrain URL'si!")
            return
        
        LOGGER.info(f"Pixeldrain dosya ID: {file_id}")
        
        # Dosya bilgilerini al
        file_info = await get_file_info(file_id)
        original_filename = None
        if file_info:
            original_filename = file_info.get('name', None)
        
        # Dosya adını belirle
        if custom_filename:
            # Kullanıcı özel ad vermiş
            final_filename = custom_filename
        elif original_filename:
            # Sitedeki orijinal ad
            final_filename = original_filename
        else:
            # Fallback
            final_filename = f"pixeldrain_{file_id}"
        
        # .mp4 uzantısını ekle/normalize et
        # Mevcut uzantıyı kaldır ve her zaman .mp4 ekle
        base_name = os.path.splitext(final_filename)[0]
        final_filename = base_name + '.mp4'
        
        LOGGER.info(f"Son dosya adı: {final_filename}")
        
        # Direkt indirme URL'si
        download_url = get_direct_download_url(file_id)
        LOGGER.info(f"İndirme URL'si: {download_url}")
        
        # Proxy manager başlat
        proxy_manager = None
        if PIXELDRAIN_USE_PROXY:
            await status_msg.edit_text("🔄 Proxy sistemi hazırlanıyor...")
            proxy_manager = ProxyManager(
                manual_proxies=PIXELDRAIN_PROXY_LIST,
                auto_fetch=PIXELDRAIN_AUTO_PROXY
            )
            await proxy_manager.initialize()
        
        # İndirme yolu
        random_suffix = str(int(time.time()))
        temp_filename = f"pixeldrain_{file_id}_{random_suffix}.mp4"
        output_path = os.path.join(DOWNLOAD_LOCATION, str(message.from_user.id), temp_filename)
        
        # Dizin oluştur
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Progress mesajı için değişkenler
        last_progress_text = ""
        last_update_time = time.time()
        
        async def progress_callback(progress_info: dict):
            """Progress güncelleme callback"""
            nonlocal last_progress_text, last_update_time
            
            current_time = time.time()
            # Her 2 saniyede bir güncelle
            if current_time - last_update_time < 2:
                return
            
            try:
                # Progress bar oluştur
                percent = int(progress_info.get('percent', 0))
                bar_length = 24
                filled = int(bar_length * percent / 100)
                bar = "━" * filled + "░" * (bar_length - filled)
                
                # Mesaj metni
                text = "📥 **İndiriliyor...**\n\n"
                text += f"📊 **Boyut:** {progress_info.get('total', 'N/A')}\n"
                text += f"⬇️ **İndirilen:** {progress_info.get('downloaded', 'N/A')} ({percent}%)\n"
                text += f"⚡ **Hız:** {progress_info.get('speed', 'N/A')}/s\n"
                text += f"⏱ **Kalan Süre:** {progress_info.get('eta', 'N/A')}\n"
                text += f"🔗 **Bağlantı:** {progress_info.get('connections', 'N/A')}\n\n"
                text += f"{bar} {percent}%"
                
                # Aynı mesajı tekrar gönderme
                if text != last_progress_text:
                    await status_msg.edit_text(text)
                    last_progress_text = text
                    last_update_time = current_time
                    
            except Exception as e:
                LOGGER.debug(f"Progress güncelleme hatası: {e}")
        
        # İndirmeyi başlat
        await status_msg.edit_text("📥 **aria2c ile indirme başlıyor...**\n\n"
                                   f"🔗 Bağlantı: {PIXELDRAIN_ARIA2C_CONNECTIONS}\n"
                                   f"🔒 Proxy: {'Aktif' if PIXELDRAIN_USE_PROXY else 'Kapalı'}")
        
        success, error = await download_with_aria2c(
            url=download_url,
            output_path=output_path,
            proxy_manager=proxy_manager,
            progress_callback=progress_callback,
            max_retries=3
        )
        
        if not success:
            await status_msg.edit_text(f"❌ İndirme başarısız!\n\n**Hata:** {error}")
            return
        
        # Dosya kontrolü
        if not os.path.exists(output_path):
            await status_msg.edit_text("❌ İndirilen dosya bulunamadı!")
            return
        
        file_size = os.path.getsize(output_path)
        LOGGER.info(f"Dosya indirildi: {output_path} ({humanbytes(file_size)})")
        
        # Dosya boyutu kontrolü
        if file_size > TG_MAX_FILE_SIZE:
            await status_msg.edit_text(
                f"❌ Dosya çok büyük!\n\n"
                f"**Boyut:** {humanbytes(file_size)}\n"
                f"**Limit:** {humanbytes(TG_MAX_FILE_SIZE)}"
            )
            # Dosyayı sil
            try:
                os.remove(output_path)
            except:
                pass
            return
        
        # Video metadata al
        try:
            metadata = VideoMetaData(output_path)
            duration = metadata.get_duration()
            width = metadata.get_width()
            height = metadata.get_height()
        except Exception as e:
            LOGGER.warning(f"Video metadata alınamadı: {e}")
            duration = 0
            width = 0
            height = 0
        
        # Thumbnail al
        try:
            thumbnail = await DocumentThumb(bot, message)
        except Exception as e:
            LOGGER.warning(f"Thumbnail alınamadı: {e}")
            thumbnail = None
        
        # Yükleme başlat
        start_time = time.time()
        await status_msg.edit_text(
            f"✅ İndirme tamamlandı!\n\n"
            f"**Dosya:** {final_filename}\n"
            f"**Boyut:** {humanbytes(file_size)}\n\n"
            f"📤 Telegram'a video olarak yükleniyor... 0%"
        )
        
        # Video olarak yükle
        try:
            await bot.send_video(
                chat_id=message.chat.id,
                video=output_path,
                caption=f"📹 **{final_filename}**\n\n"
                        f"🔗 Pixeldrain ID: `{file_id}`\n"
                        f"📊 Boyut: {humanbytes(file_size)}",
                duration=duration,
                width=width,
                height=height,
                thumb=thumbnail,
                file_name=final_filename,
                reply_to_message_id=message.id,
                progress=progress_for_pyrogram,
                progress_args=(
                    "📤 **Yükleniyor...**",
                    status_msg,
                    start_time
                )
            )
            await status_msg.delete()
            
        except Exception as e:
            LOGGER.error(f"Telegram yükleme hatası: {e}")
            await status_msg.edit_text(f"❌ Telegram'a yükleme başarısız!\n\n**Hata:** {str(e)}")
        
        finally:
            # Temizlik
            try:
                if os.path.exists(output_path):
                    os.remove(output_path)
                    LOGGER.info(f"Dosya silindi: {output_path}")
            except Exception as e:
                LOGGER.error(f"Dosya silme hatası: {e}")
            
            # Thumbnail temizle
            if thumbnail and os.path.exists(thumbnail):
                try:
                    os.remove(thumbnail)
                except Exception as e:
                    LOGGER.error(f"Thumbnail silme hatası: {e}")
                
    except Exception as e:
        LOGGER.error(f"Pixeldrain indirme hatası: {str(e)}")
        try:
            await status_msg.edit_text(f"❌ Bir hata oluştu!\n\n**Hata:** {str(e)}")
        except Exception as edit_error:
            LOGGER.error(f"Status mesajı düzenlenemedi: {edit_error}")
