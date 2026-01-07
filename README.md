<p align="center">
  <img src="https://id.piktid.com/logo.svg" alt="Model Swap by PiktID logo" width="150">
  </br>
  <h3 align="center"><a href="https://on-model.com">Model Swap by PiktID</a></h3>
</p>

# Model Swap - v1.0
[![Official Website](https://img.shields.io/badge/Official%20Website-piktid.com-blue?style=flat&logo=world&logoColor=white)](https://piktid.com)
[![Discord Follow](https://dcbadge.vercel.app/api/server/FJU39e9Z4P?style=flat)](https://discord.com/invite/FJU39e9Z4P)

Model Swap implementation by PiktID for processing Product Detail Page (PDP) images. This script performs automated model-swap on multiple images in a folder using the <a href="https://v2.api.piktid.com">PiktID v2 API</a>.

This implementation uses the <a href="https://docs.piktid.com/docs/v2">PiktID v2 API</a> for model-swap processing.

## Getting Started

The following instructions suppose you have already installed a recent version of Python. For a general overview, please visit the <a href="https://docs.piktid.com/docs/v2">API documentation</a>.
To use any PiktID API, authentication credentials are required.

> **Step 0** - Register <a href="https://studio.piktid.com">here</a>. 10 credits are given for free to all new users.

> **Step 1** - Clone the Model Swap repository
```bash
# Installation commands
$ git clone https://github.com/piktid/model-swap.git
$ cd model-swap
```

> **Step 2** - Prepare your PDP folder with images

Ensure your input folder contains Product Detail Page images (JPG, JPEG, or PNG format). The script automatically filters out images that don't contain models:
- Images with `_INTERNAL_` in the filename are excluded
- Images with `_NONMODEL_` in the filename are excluded

> **Step 3** - Choose your identity

You can either use an existing identity code from your gallery or upload a new identity image:

**Option A: Using an existing identity code**
```bash
$ python model_swap.py \
  --input-folder PDP/ARTICLE123 \
  --username your_email@example.com \
  --password your_password \
  --identity-code PiktidPremium \
  --output-folder results/ARTICLE123
```

**Option B: Uploading a new identity image**
```bash
$ python model_swap.py \
  --input-folder PDP/ARTICLE123 \
  --username your_email@example.com \
  --password your_password \
  --identity-image identities/female/LisaPremium.jpg \
  --output-folder results/ARTICLE123
```

> **Step 4** - Monitor the processing

The script will automatically:
1. Authenticate with the API
2. Create a project (or use existing one)
3. Upload all PDP images from the input folder
4. Upload or verify the identity
5. Create a model-swap job
6. Monitor job progress
7. Download results to the output folder

You'll see progress updates in the console. Once complete, processed images will be saved to your output folder.

> **Step 5** - Review results

Results are saved to the output folder with the following structure:
```
output/
├── image1_v0.jpg          # Processed image (version 0)
├── image2_v0.jpg          # Processed image (version 0)
├── image3_v0.jpg          # Processed image (version 0)
└── metadata.json          # Complete job information and results
```

The `metadata.json` file contains:
- Job ID and status
- Processing results for each image
- Quality scores and processing times
- Image URLs and metadata

## Post-Processing

If you want to enable post-processing (skin equalization) for better results:
```bash
$ python model_swap.py \
  --input-folder PDP/ARTICLE123 \
  --username your_email@example.com \
  --password your_password \
  --identity-code PiktidPremium \
  --output-folder results/ARTICLE123 \
  --post-process
```

## Command Line Options

```
--input-folder      Path to folder containing PDP images (required)
--username          API username (required)
--password          API password (required)
--identity-code     Existing identity code to use (optional)
--identity-image    Path to identity image file to upload (optional)
--output-folder     Output folder for results (default: output)
--base-url          API base URL (default: https://v2.api.piktid.com)
--post-process      Enable post-processing (default: False)
```

**Note:** Either `--identity-code` or `--identity-image` must be provided.

## Usage Examples

### Example 1: Basic Processing

Process a PDP folder with an existing identity code:
```bash
$ python model_swap.py \
  --input-folder PDP/P1KT1D-Y22 \
  --username your_email@example.com \
  --password your_password \
  --identity-code PiktidPremium \
  --output-folder output/P1KT1D-Y22
```

### Example 2: Upload New Identity

Upload a new identity and process images:
```bash
$ python model_swap.py \
  --input-folder PDP/P1KT1D-Y22 \
  --username your_email@example.com \
  --password your_password \
  --identity-image identities/female/LisaPremium.jpg \
  --output-folder output/P1KT1D-Y22
```

### Example 3: With Post-Processing

Enable post-processing (skin equalization):
```bash
$ python model_swap.py \
  --input-folder PDP/P1KT1D-Y22 \
  --username your_email@example.com \
  --password your_password \
  --identity-code PiktidPremium \
  --output-folder output/P1KT1D-Y22 \
  --post-process
```

### Example 4: Custom API Server

Process images on a custom API server:
```bash
$ python model_swap.py \
  --input-folder PDP/P1KT1D-Y22 \
  --identity-code PiktidPremium \
  --output-folder output/P1KT1D-Y22 \
  --base-url https://v2.api.piktid.com \
  --username your_email@example.com \
  --password your_password \
  --post-process
```

## Troubleshooting

### Authentication Failed
```
Authentication failed: 401
```
**Solution:** Check your username and password. Verify the API server is running and accessible.

### No Images Found
```
No processable images found in PDP/ARTICLE123
```
**Solution:** 
- Verify the input folder path is correct
- Check that the folder contains image files (JPG, JPEG, PNG)
- Note: Images with `_INTERNAL_` or `_NONMODEL_` in filenames are automatically excluded

### Identity Not Found
```
Error checking identity: ...
```
**Solution:** 
- Verify the identity code exists in your gallery
- Or provide an `--identity-image` path to upload a new identity

### Job Timeout
```
Timeout: Job took longer than 1200 seconds
```
**Solution:** The job may be taking longer than expected. Check the API server status. You can modify the `max_wait_time` parameter in the `wait_for_job` method if needed.

### Connection Errors
```
Authentication error: Connection refused
```
**Solution:** 
- Verify the API server is running
- Check the `--base-url` is correct
- Ensure network connectivity to the API server

## Error Handling

The script will exit with an error code if:
- Authentication fails
- No images are found in the input folder
- Identity upload/verification fails
- Job creation fails
- Job does not complete successfully
- Results download fails

Check the console output for detailed error messages.

## Contact
office@piktid.com
