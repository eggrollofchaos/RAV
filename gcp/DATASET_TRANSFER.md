# Dataset Transfer: Azure to GCS

How to get CheXpert datasets into the GCS bucket so training VMs can access them.

## Background

CheXpert is hosted by Stanford AIMI on Azure Blob Storage. Training VMs pull data from GCS at startup, so datasets need to be in GCS first.

There are two versions:
- **CheXpert Small** (~11 GB) — downsampled images, same labels and splits. Sufficient for baseline training.
- **CheXpert Full** (~471 GB) — original resolution. Needed for production-quality runs.

## CheXpert Small (Kaggle mirror)

Download from Kaggle on your local machine and sync to GCS:

```bash
# Download via Kaggle (requires Kaggle account)
# https://www.kaggle.com/datasets/ashery/chexpert

# After downloading and extracting:
gcloud storage rsync -r data/raw/chexpert gs://rav-ai-train-artifacts-488706/datasets/chexpert/raw
gcloud storage rsync -r data/processed gs://rav-ai-train-artifacts-488706/datasets/chexpert/processed
```

## CheXpert Full (Azure transfer via GCE VM)

Downloading 471 GB locally is impractical. Use a temporary GCE VM in the same region as your bucket for fast GCS upload.

### Step 1: Get a SAS URL from Stanford AIMI

1. Go to https://stanfordaimi.azurewebsites.net/datasets/8cbd9ed4-2eb9-4565-affc-111cf4f7ebe2
2. Accept the Data Use Agreement.
3. Copy the Azure SAS URL. It will look like:
   ```
   https://aimistanforddatasets01.blob.core.windows.net/chexpertchestxrays-u20210408?sv=...&sig=...&se=...&sp=rl
   ```
   Note: SAS URLs expire (typically 30 days). Generate a fresh one if yours has expired.

### Step 2: Create a temporary transfer VM

```bash
gcloud compute instances create chexpert-transfer \
  --zone=us-east1-c \
  --machine-type=e2-standard-4 \
  --boot-disk-size=500GB \
  --scopes=storage-full \
  --network-interface=network=default,stack-type=IPV4_ONLY
```

### Step 3: SSH into the VM

```bash
gcloud compute ssh chexpert-transfer --zone=us-east1-c --ssh-flag="-v"
```

The `-v` flag is recommended — without it the connection can appear to hang silently during key propagation (especially on first connect). This is normal and can take 1-2 minutes.

### Step 4: Install azcopy on the VM

The `aka.ms` redirect URLs do not work reliably from GCE. Use a direct GitHub release URL instead.

```bash
sudo apt-get update && sudo apt-get install -y libsecret-1-0

curl -L https://github.com/Azure/azure-storage-azcopy/releases/download/v10.27.1/azcopy_linux_amd64_10.27.1.tar.gz \
  -o /tmp/azcopy.tar.gz
tar xzf /tmp/azcopy.tar.gz -C /tmp
sudo mv /tmp/azcopy_linux_amd64_*/azcopy /usr/local/bin/
azcopy --version
```

Important notes:
- Use the **non-SE** (non-security-enhanced) build. The `_se_` builds (v10.32+) crash with a nil pointer dereference on certain SAS URL formats.
- `libsecret-1-0` is a required shared library; the VM image does not include it by default.

### Step 5: Download from Azure

Use **single quotes** around the SAS URL to prevent shell expansion of `?`, `&`, and `=` characters:

```bash
azcopy copy '<PASTE_FULL_SAS_URL_HERE>' /tmp/chexpert-full \
  --recursive=true --from-to=BlobLocal --log-level=WARNING
```

This takes roughly 15-45 minutes depending on VM networking.

### Step 6: Upload to GCS

```bash
gcloud storage rsync -r /tmp/chexpert-full/ \
  gs://rav-ai-train-artifacts-488706/datasets/chexpert-full/raw/
```

### Step 7: (Optional) Generate and upload processed CSVs

If you have the repo cloned on the VM, or have copied the prepare script:

```bash
# Find the CheXpert root (directory containing train.csv)
find /tmp/chexpert-full -name train.csv -maxdepth 3

# Run prepare script
python3 scripts/prepare_chexpert_data.py \
  --chexpert-root /tmp/chexpert-full/<path-to-dir-with-train.csv> \
  --output-dir /tmp/chexpert-full/processed

gcloud storage rsync -r /tmp/chexpert-full/processed/ \
  gs://rav-ai-train-artifacts-488706/datasets/chexpert-full/processed/
```

### Step 8: Clean up the VM

Exit the SSH session, then from your local machine:

```bash
gcloud compute instances delete chexpert-transfer --zone=us-east1-c --quiet
```

A stopped VM costs nothing except disk (~$0.04/GB/month), so there is no rush if you want to keep it around for debugging.

## Using the datasets in training jobs

The training job command in `gcp/rav_spot.env` syncs data from GCS before training starts. Update the GCS paths to match which dataset you uploaded:

```bash
# For CheXpert Small:
gcloud storage rsync -r gs://rav-ai-train-artifacts-488706/datasets/chexpert/raw data/raw/chexpert
gcloud storage rsync -r gs://rav-ai-train-artifacts-488706/datasets/chexpert/processed data/processed

# For CheXpert Full:
gcloud storage rsync -r gs://rav-ai-train-artifacts-488706/datasets/chexpert-full/raw data/raw/chexpert
gcloud storage rsync -r gs://rav-ai-train-artifacts-488706/datasets/chexpert-full/processed data/processed
```

## Troubleshooting

**`gcloud compute ssh` hangs with no output:**
Add `--ssh-flag="-v"` for verbose output. First connection to a new VM takes 1-2 minutes for SSH key propagation.

**azcopy `unexpected end of data` or gzip errors:**
The `aka.ms` redirect returns HTML instead of a tarball from some networks. Use the direct GitHub release URL as shown above.

**azcopy segfault / nil pointer dereference:**
Use the non-SE build (v10.27.1). The SE builds have a bug with certain SAS URL patterns. Also ensure the SAS URL is wrapped in single quotes with no other unexpected symbols.

**`BUCKET not set` when running fetch script on VM:**
The VM doesn't have `gcp/rav_spot.env`. Export it manually: `export BUCKET=rav-ai-train-artifacts-488706`

**VM has no internet access:**
Ensure the VM was created with `--network-interface=network=default,stack-type=IPV4_ONLY` to get an external IP.

**SAS URL expired:**
Generate a fresh one from the Stanford AIMI download page. They typically expire after 30 days.
