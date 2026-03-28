# Enhanced ffmpeg Logging Implementation

## Overview
This implementation adds comprehensive logging to all ffmpeg operations in the urlbot project as requested. The changes provide detailed tracking of video/audio conversion processes with enhanced error reporting and debugging capabilities.

## Changes Made

### 1. Enhanced Log Format
**Updated in all relevant files:**
- `functions/ffmpeg.py`
- `plugins/ytdlp_button.py` 
- `plugins/dl_button.py`
- `plugins/log.py`

**New Format:**
```
%(asctime)s - %(filename)s:%(lineno)d - %(name)s - %(levelname)s - %(message)s
```

**Example Output:**
```
2025-07-10 19:17:07,123 - ffmpeg.py:142 - functions.ffmpeg - DEBUG - Starting ffmpeg screenshot command: ffmpeg -ss 5 -i video.mp4 -vframes 1 output.jpg
```

### 2. Enhanced ffmpeg Functions in `functions/ffmpeg.py`

#### `place_water_mark()` Function
- **Start Logging:** Logs input parameters and operation start
- **Command Logging:** Logs both watermark shrink and overlay commands
- **Process Monitoring:** Captures and logs stdout/stderr at DEBUG level
- **Error Handling:** Logs errors with return codes and stack traces
- **Success Logging:** Confirms successful completion

#### `take_screen_shot()` Function  
- **Start Logging:** Logs video file, output directory, and timestamp
- **Command Logging:** Logs ffmpeg screenshot command
- **Process Monitoring:** Captures and logs stdout/stderr at DEBUG level
- **Error Handling:** Logs errors with return codes and stack traces
- **Success Logging:** Confirms screenshot generation

#### `cult_small_video()` Function
- **Start Logging:** Logs video trimming parameters
- **Command Logging:** Logs ffmpeg video trim command
- **Process Monitoring:** Captures and logs stdout/stderr at DEBUG level
- **Error Handling:** Logs errors with return codes and stack traces
- **Success Logging:** Confirms video trimming completion

### 3. Enhanced yt-dlp Subprocess in `plugins/ytdlp_button.py`

#### yt-dlp Process Logging
- **Start Logging:** Logs full yt-dlp command before execution
- **Process Monitoring:** Logs process PID and tracks execution
- **Output Logging:** Captures stdout/stderr at DEBUG level
- **Error Handling:** Logs failures with return codes and stack traces
- **Success Logging:** Confirms successful download completion

## Key Features

### 1. Detailed Process Tracking
- Logs before ffmpeg/yt-dlp operations start
- Logs during process execution with stdout/stderr
- Logs after successful completion or failure

### 2. Debug Level Output Capture
- All ffmpeg stdout/stderr captured at DEBUG level
- Full command strings logged for reproducibility
- Process return codes tracked

### 3. Comprehensive Error Logging
- ERROR level logging for all failures
- Full stack traces included for debugging
- Return codes and error messages preserved

### 4. Enhanced Log Format
- Filename and line number for precise error location
- Timestamp for operation timing
- Log level for filtering capabilities

## Files Modified

1. **`functions/ffmpeg.py`**
   - Updated logging format
   - Enhanced all 3 ffmpeg functions with detailed logging
   - Added error handling with stack traces

2. **`plugins/ytdlp_button.py`**
   - Updated logging format
   - Enhanced yt-dlp subprocess execution logging
   - Added process tracking and error handling

3. **`plugins/dl_button.py`**
   - Updated logging format for consistency

4. **`plugins/log.py`**
   - Updated logging format for consistency

## Minimal Change Approach

The implementation follows the requirement for minimal changes:
- ✅ No existing functionality removed or modified
- ✅ Only logging enhancements added
- ✅ Preserved all original error handling
- ✅ No new dependencies added
- ✅ Backward compatible with existing code

## Example Log Output

```
2025-07-10 19:17:07,123 - ffmpeg.py:97 - functions.ffmpeg - DEBUG - Starting watermark placement: input_file=video.mp4, output_file=output.mp4, water_mark_file=logo.png
2025-07-10 19:17:07,124 - ffmpeg.py:108 - functions.ffmpeg - DEBUG - Starting ffmpeg watermark shrink command: ffmpeg -i logo.png -y -v quiet -vf scale=1920*0.5:-1 output.mp4.watermark.png
2025-07-10 19:17:07,125 - ffmpeg.py:120 - functions.ffmpeg - DEBUG - ffmpeg watermark shrink stdout: 
2025-07-10 19:17:07,125 - ffmpeg.py:121 - functions.ffmpeg - DEBUG - ffmpeg watermark shrink stderr: 
2025-07-10 19:17:07,125 - ffmpeg.py:130 - functions.ffmpeg - DEBUG - ffmpeg watermark shrink completed successfully
2025-07-10 19:17:07,126 - ffmpeg.py:142 - functions.ffmpeg - DEBUG - Starting ffmpeg watermark overlay command: ffmpeg -i video.mp4 -i output.mp4.watermark.png -filter_complex "overlay=(main_w-overlay_w):(main_h-overlay_h)" output.mp4
2025-07-10 19:17:07,126 - ffmpeg.py:154 - functions.ffmpeg - DEBUG - ffmpeg watermark overlay stdout: 
2025-07-10 19:17:07,126 - ffmpeg.py:155 - functions.ffmpeg - DEBUG - ffmpeg watermark overlay stderr:
2025-07-10 19:17:07,126 - ffmpeg.py:164 - functions.ffmpeg - DEBUG - Watermark placement completed successfully: output.mp4
```

## Benefits

1. **Enhanced Debugging:** Detailed logs help identify issues quickly
2. **Process Monitoring:** Track ffmpeg operations in real-time
3. **Error Diagnosis:** Stack traces and return codes for troubleshooting
4. **Performance Analysis:** Timing information for optimization
5. **Audit Trail:** Complete record of all conversion operations