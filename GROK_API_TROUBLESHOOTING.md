# Grok API Troubleshooting

## Windows Encoding Issues

If you get encoding errors on Windows, run the encoding test first:

```bash
poetry run python test_encoding.py
```

This will verify that UTF-8 encoding is working correctly. The app now automatically:
- Reconfigures stdout/stderr to UTF-8 on Windows
- Sets `PYTHONUTF8=1` environment variable
- Uses UTF-8 with error handling for all file operations

If the test shows encoding issues, you can also:
1. Set environment variable before running: `set PYTHONUTF8=1`
2. Run PowerShell as: `chcp 65001` (sets console to UTF-8)
3. Use Windows Terminal instead of cmd.exe

## Quick Test

Run this to test your API connection:

```bash
poetry run python test_grok_api.py
```

This will test:
1. Basic text completion
2. Vision model
3. List available models (if supported)

## Common 400 Bad Request Issues

### 1. **Wrong Model Name**

The Grok API model names change over time. Current known models:
- `grok-beta` - Base model
- `grok-2-1212` - Grok 2 (December 2024 release)
- `grok-2-vision-1212` - Grok 2 with vision
- `grok-vision-beta` - Vision model beta

Check the [x.ai documentation](https://docs.x.ai/api) for current model names.

**Fix:** Update model names in `src/pasokon/grok_client.py`

### 2. **Image Format Issues**

The API might be picky about:
- Image data URL format (must be `data:image/[type];base64,[data]`)
- Image MIME type (jpeg vs jpg vs png)
- Image size (too large?)

**Fix:** Try using `data:image/png;base64,...` instead of jpeg, or resize images.

### 3. **Request Format**

The vision API might expect different content structure. Options:
- Text as simple string instead of array
- Different image_url structure
- Missing required fields

### 4. **API Key Issues**

- Wrong API key format
- Expired or invalid key
- Key not activated for vision models

**Test:** Run `test_grok_api.py` to verify basic API access works.

### 5. **Rate Limiting**

Even though it returns 400, it might be rate limiting.

## Manual Testing

### Using curl (Windows - PowerShell)

```powershell
$headers = @{
    "Authorization" = "Bearer YOUR-API-KEY"
    "Content-Type" = "application/json"
}

$body = @{
    model = "grok-2-1212"
    messages = @(
        @{
            role = "user"
            content = "Hello"
        }
    )
} | ConvertTo-Json -Depth 10

Invoke-WebRequest -Uri "https://api.x.ai/v1/chat/completions" -Method POST -Headers $headers -Body $body
```

### Using curl (Unix/Linux/macOS)

```bash
curl -X POST https://api.x.ai/v1/chat/completions \
  -H "Authorization: Bearer YOUR-API-KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "grok-2-1212",
    "messages": [
      {
        "role": "user",
        "content": "Hello"
      }
    ]
  }'
```

## Checking API Response

When you get the 400 error in the Gradio app, check the terminal/console output. The improved error handling will now show:
- HTTP status code
- Full error response from the API

This will tell you exactly what's wrong.

## Alternative: Check x.ai Documentation

The official documentation is at: https://docs.x.ai/api

Things to check:
1. Current base URL (is it `https://api.x.ai/v1`?)
2. Current model names
3. Vision API format (might be different from OpenAI)
4. Any beta access requirements for vision/image features

## If Image Generation API is Different

The image generation endpoint might be:
- Under a different path (not `/v1/images/generations`)
- Require a different model name
- Not yet available (still in beta)

Check if there's a separate "Aurora" or "Grok Image" API.
