# RefuelingPlatform - Deployment Guide

## Overview of Changes from Original

The original Colab notebook has been refactored into a production-ready application for Azure App Services.

| Aspect | Original (Colab) | Azure Version |
|--------|------------------|---------------|
| **Storage** | Google Drive (`/content/drive/MyDrive/data`) | Temp/Persistent Storage (`/tmp/fuel_data` or Azure File Share) |
| **Dependencies** | `google.colab` included | Azure-compatible only |
| **Port** | 7860 (Gradio default) | 8000 (Azure standard) |
| **Logging** | Console output | File-based rotating logs |
| **Deployment** | Interactive Jupyter notebook | Docker container |
| **Config** | Hardcoded paths | Environment variables |

## Key Features

✅ Photo upload and storage  
✅ Location/Car/Tank selection with GPS integration  
✅ Image history and gallery viewing  
✅ OCR processing for gauge readings  
✅ Comprehensive logging  
✅ Production-ready error handling  

## Quick Start - Local Testing

### Prerequisites
- Python 3.11+
- Docker (optional)
- Git

### Option 1: Run Locally (No Docker)

```bash
# Clone repository
git clone https://github.com/chiujonathanjs-cpu/RefuelingPlatform.git
cd RefuelingPlatform

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run application
python app.py
```

Access at: `http://localhost:7860`

### Option 2: Run with Docker

```bash
# Build image
docker build -t refuelingplatform:latest .

# Run container
docker run -p 8000:8000 \
  -e PORT=8000 \
  -e ROOT_FOLDER=/app/fuel_data \
  -v $(pwd)/fuel_data:/app/fuel_data \
  refuelingplatform:latest
```

Access at: `http://localhost:8000`

## Deployment to Azure

### Quick Deployment Script

```bash
#!/bin/bash

# Configuration
RG="RefuelingPlatformRG"
REGISTRY="refuelingregistry"
APP="refuelingplatform"
LOCATION="eastus"

# Login
az login

# Create resource group
az group create --name $RG --location $LOCATION

# Create container registry
az acr create --resource-group $RG --name $REGISTRY --sku Basic

# Build and push
az acr build --registry $REGISTRY --image $APP:latest .

# Create app service plan
az appservice plan create --name "${APP}Plan" --resource-group $RG --sku B2 --is-linux

# Create web app
az webapp create \
  --resource-group $RG \
  --plan "${APP}Plan" \
  --name $APP \
  --deployment-container-image-name-user "${REGISTRY}.azurecr.io/${APP}:latest"

# Configure container
USER=$(az acr credential show --name $REGISTRY --query username -o tsv)
PASS=$(az acr credential show --name $REGISTRY --query passwords[0].value -o tsv)

az webapp config container set \
  --resource-group $RG \
  --name $APP \
  --docker-custom-image-name "${REGISTRY}.azurecr.io/${APP}:latest" \
  --docker-registry-server-url "https://${REGISTRY}.azurecr.io" \
  --docker-registry-server-user $USER \
  --docker-registry-server-password $PASS

# Set environment variables
az webapp config appsettings set \
  --resource-group $RG \
  --name $APP \
  --settings PORT=8000 ROOT_FOLDER=/home/site/wwwroot/fuel_data

echo "Deployment complete! Access at: https://${APP}.azurewebsites.net"
```

## File Structure

```
RefuelingPlatform/
├── app.py                  # Main Gradio application
├── requirements.txt        # Python dependencies
├── Dockerfile             # Container configuration
├── .dockerignore          # Docker build exclusions
├── azure-deployment.md    # Comprehensive deployment guide
├── DEPLOYMENT.md          # This file
└── README.md              # Project overview
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | 7860 | Server port |
| `ROOT_FOLDER` | `/tmp/fuel_data` | Data storage directory |
| `WEBSITES_PORT` | 8000 | Azure App Services port |

## Performance Notes

- **Memory**: Minimum 512 MB (B1 tier)
- **CPU**: 1 core recommended (B2+ for production)
- **Storage**: 50+ GB recommended for fuel data
- **OCR Processing**: PaddleOCR loads ~200 MB models on first run

## Logging

Logs are written to `{ROOT_FOLDER}/app.log` with rotating file handler:
- Max file size: 10 MB
- Backup count: 5 files

Access logs:
```bash
# Local
tail -f /tmp/fuel_data/app.log

# Azure
az webapp log tail --resource-group <RG> --name <APP>
```

## Troubleshooting

### Application won't start
```bash
# Check logs
docker logs <container-id>

# Or in Azure
az webapp log tail --resource-group <RG> --name <APP>
```

### Port already in use
```bash
# Change PORT environment variable
export PORT=8080
python app.py
```

### OCR model loading fails
- Requires internet connection for first load
- Models cached in `~/.paddlex/official_models/`
- Size: ~500 MB

### Storage issues
- Ensure `/tmp/fuel_data` exists with write permissions
- For Azure, configure Azure File Share mount

## Security Considerations

1. **HTTPS Only**: Enable in Azure portal or via CLI
2. **Authentication**: Consider adding user auth layer
3. **Data Privacy**: Sensitive images should be encrypted at rest
4. **API Keys**: Never commit credentials

## Scaling

### Vertical Scaling (Larger Instance)
```bash
az appservice plan update \
  --name <plan-name> \
  --resource-group <rg> \
  --sku B3
```

### Horizontal Scaling (Multiple Instances)
```bash
az appservice plan update \
  --name <plan-name> \
  --resource-group <rg> \
  --number-of-workers 3
```

## Monitoring

### Azure Application Insights
```bash
az monitor app-insights component create \
  --app refueling-insights \
  --resource-group <rg>
```

### Container Logs
```bash
az container logs --name refuelingplatform --resource-group <rg>
```

## Backup and Disaster Recovery

### Backup Application Files
```bash
az webapp config backup create \
  --resource-group <rg> \
  --name <app> \
  --backup-name manual-backup
```

### Restore from Backup
```bash
az webapp config backup restore \
  --resource-group <rg> \
  --name <app> \
  --backup-id <backup-id>
```

## Cost Estimation

**Monthly costs (approximate):**
- App Service Plan (B2): ~$20-30
- Container Registry: ~$5
- Storage (100 GB): ~$2
- **Total: $27-37/month**

## Next Steps

1. Configure persistent storage backend
2. Implement user authentication
3. Setup CI/CD pipeline (GitHub Actions/Azure DevOps)
4. Configure custom domain
5. Enable SSL/TLS certificate
6. Setup monitoring and alerts
7. Implement database backend for metadata

## Support

For issues or questions:
1. Check Azure portal diagnostics
2. Review application logs
3. Consult `azure-deployment.md` for detailed steps
4. Open GitHub issue with logs and configuration

---

**Last Updated**: 2026-05-22  
**Version**: 1.0.0
