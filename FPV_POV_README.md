# FPV POV Image Generator

Automated workflow for generating first-person POV character reference images using Grok and Grok Imagine.

## Features

- 🎯 **Automated Prompt Generation**: Uses your FPV POV skills to generate optimized prompts
- 🖼️ **Batch Image Generation**: Generate multiple variations in one go
- 🔍 **Intelligent Review**: Automatically review failed images and get corrected prompts
- 🎨 **Phase 2 Support**: Green-zone enhancement workflow for difficult elements (hair, etc.)
- 💾 **Iterative Workflow**: Keep refining until you get the perfect image
- 🔄 **Flexible Integration**: Easy to incorporate manual Photoshop edits between iterations

## Setup

### 1. Install Dependencies

```bash
# Install the package with new dependencies
pip install -e .
```

### 2. Get Your Grok API Key

1. Sign up at [x.ai](https://x.ai)
2. Generate an API key
3. Either:
   - Set the environment variable: `export XAI_API_KEY=your-api-key-here`
   - Or enter it in the app's Configuration section

### 3. Prepare Your Skills

Make sure you have:
- `fpv-pov-image.md` - Your prompt engineering skill
- `fpv-pov-review.md` - Your review/correction skill

These files should be in the project root directory.

## Usage

### Launch the App

```bash
pasokon fpv-pov
```

The Gradio interface will open in your browser at `http://127.0.0.1:7860`

### Workflow

#### Phase 1: Base Image Generation

1. **Tab 1 - Generate Prompt**
   - Upload your character reference image
   - Optionally upload additional character references
   - Describe your scene
   - Click "Generate Prompt"
   - Review and edit the prompt if needed

2. **Tab 2 - Generate Images**
   - The prompt is automatically copied from Tab 1
   - Choose how many images to generate (default: 3)
   - Click "Generate Images"
   - Review the results

3. **Tab 3 - Review & Correct**
   - If images have errors, click "Review & Generate Corrected Prompt"
   - The app will analyze what went wrong and provide a better prompt
   - Copy the corrected prompt back to Tab 2
   - Regenerate images

4. **Iterate**
   - Repeat steps 2-3 until you have a solid base image
   - Save good results to your computer between iterations
   - You can also upload manually edited images (e.g., from Photoshop) for review

#### Phase 2: Enhancements (Optional)

For elements that frequently hallucinate (like hair fringe):

1. **Tab 4 - Phase 2: Enhancements**
   - Take your best base image from Phase 1
   - Open it in Photoshop/GIMP
   - Mark green zones where you want elements added
   - Upload the green-marked image as @image1
   - Upload your original character reference as @image2
   - Describe what to add in the green zones
   - Generate the enhancement prompt
   - Use this prompt in Tab 2 to generate enhanced images

## API Reference

### GrokClient

The `GrokClient` class handles all API interactions:

```python
from pasokon.grok_client import GrokClient

# Initialize
client = GrokClient(api_key="your-key")

# Generate a prompt
prompt = client.generate_prompt(
    reference_image="path/to/character.jpg",
    scene_description="Your scene description",
    skill_content=prompt_skill_text,
    additional_images=["path/to/image2.jpg"]  # optional
)

# Generate images
images = client.generate_images(
    prompt=prompt,
    reference_image="path/to/character.jpg",
    num_images=3,
    additional_images=["path/to/image2.jpg"]  # optional
)

# Review and get corrections
corrected = client.review_images(
    failed_images=["path/to/failed1.jpg", "path/to/failed2.jpg"],
    original_prompt=original_prompt,
    scene_description=scene_description,
    reference_image="path/to/character.jpg",
    skill_content=review_skill_text
)
```

## Tips

- **Save intermediate results**: Download good images between iterations
- **Start simple**: Generate clean bases first, add complex elements later
- **Use Photoshop freely**: You can manually edit images and upload them for review
- **Green zones work**: For stubborn elements, use the Phase 2 green-zone technique
- **Iterate patiently**: FPV POV images often need 2-4 rounds to get right
- **Edit prompts**: Don't be afraid to manually tweak generated prompts

## Troubleshooting

### "API key not configured"
- Make sure you've either set `XAI_API_KEY` environment variable or entered the key in the Configuration section

### "Images not generating"
- Check your API key is valid
- Ensure you have API credits
- Check the console for detailed error messages

### "Review not working"
- Make sure you have either generated images in Tab 2 or uploaded failed images in Tab 3
- Verify your reference image is still available

### "Prompt looks wrong"
- You can always manually edit generated prompts before using them
- The skills are just templates - feel free to override

## Architecture

```
src/pasokon/
├── grok_client.py       # Grok API integration
├── gradio_app.py        # Main Gradio interface
└── commands/
    └── fpv_pov.py       # CLI command to launch app
```

The app maintains state across tabs so you don't need to re-upload images for each step.

## Example Workflow

1. Launch: `pasokon fpv-pov`
2. Configure API key
3. Upload character reference + describe scene → Get prompt
4. Generate 3 images
5. Review shows issues → Get corrected prompt
6. Generate 3 more images with correction
7. One looks good! Download it
8. Open in Photoshop, mark green zones for hair
9. Upload to Phase 2 → Get enhancement prompt
10. Generate final enhanced images
11. Done! 🎉

## Future Enhancements

Potential improvements:
- Direct download buttons in the UI
- Prompt history/favorites
- Automatic green-zone detection
- Integration with image editing tools
- Batch processing multiple scenes
- Cost tracking

## License

Same as the parent project.
