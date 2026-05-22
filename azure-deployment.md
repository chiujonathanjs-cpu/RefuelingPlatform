# Azure App Services Deployment Guide

This guide provides step-by-step instructions to deploy the RefuelingPlatform application to Azure App Services using Docker containers.

## Prerequisites

- Azure Account with active subscription
- Azure CLI installed ([Download](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli))
- Docker installed locally
- Git installed

## Step 1: Prepare Azure Resources

### 1.1 Login to Azure
```bash
az login
```

### 1.2 Set Variables (Update with your values)
```bash
RESOURCE_GROUP="RefuelingPlatformRG"
REGISTRY_NAME="refuelingregistry"
APP_SERVICE_PLAN="RefuelingServicePlan"
APP_SERVICE_NAME="refuelingplatform"
LOCATION="eastus"
```

### 1.3 Create Resource Group
```bash
az group create \
  --name $RESOURCE_GROUP \
  --location $LOCATION
```

### 1.4 Create Container Registry
```bash
az acr create \
  --resource-group $RESOURCE_GROUP \
  --name $REGISTRY_NAME \
  --sku Basic
```

## Step 2: Build and Push Docker Image

### 2.1 Login to Azure Container Registry
```bash
az acr login --name $REGISTRY_NAME
```

### 2.2 Build Docker Image
```bash
az acr build \
  --registry $REGISTRY_NAME \
  --image refuelingplatform:latest \
  --file Dockerfile .
```

## Step 3: Create App Service

### 3.1 Create App Service Plan
```bash
az appservice plan create \
  --name $APP_SERVICE_PLAN \
  --resource-group $RESOURCE_GROUP \
  --sku B2 \
  --is-linux
```

### 3.2 Create Web App
```bash
az webapp create \
  --resource-group $RESOURCE_GROUP \
  --plan $APP_SERVICE_PLAN \
  --name $APP_SERVICE_NAME \
  --deployment-container-image-name-user "${REGISTRY_NAME}.azurecr.io/refuelingplatform:latest"
```

### 3.3 Configure Container Registry Access
```bash
REGISTRY_USERNAME=$(az acr credential show --name $REGISTRY_NAME --query username -o tsv)
REGISTRY_PASSWORD=$(az acr credential show --name $REGISTRY_NAME --query passwords[0].value -o tsv)

az webapp config container set \
  --resource-group $RESOURCE_GROUP \
  --name $APP_SERVICE_NAME \
  --docker-custom-image-name "${REGISTRY_NAME}.azurecr.io/refuelingplatform:latest" \
  --docker-registry-server-url "https://${REGISTRY_NAME}.azurecr.io" \
  --docker-registry-server-user $REGISTRY_USERNAME \
  --docker-registry-server-password $REGISTRY_PASSWORD
```

## Step 4: Configure Application Settings

### 4.1 Set Environment Variables
```bash
az webapp config appsettings set \
  --resource-group $RESOURCE_GROUP \
  --name $APP_SERVICE_NAME \
  --settings PORT=8000 \
    ROOT_FOLDER=/home/site/wwwroot/fuel_data \
    WEBSITES_PORT=8000
```

### 4.2 Enable Continuous Deployment (Optional)
```bash
az webapp deployment container config \
  --resource-group $RESOURCE_GROUP \
  --name $APP_SERVICE_NAME \
  --enable-cd true
```

## Step 5: Configure Persistent Storage (Optional)

For persistent data storage across container restarts:

### 5.1 Create Storage Account
```bash
STORAGE_ACCOUNT="refuelingstorage"

az storage account create \
  --name $STORAGE_ACCOUNT \
  --resource-group $RESOURCE_GROUP \
  --location $LOCATION
```

### 5.2 Create File Share
```bash
az storage share create \
  --name "fuel-data" \
  --account-name $STORAGE_ACCOUNT
```

### 5.3 Mount Storage to App Service
```bash
STORAGE_KEY=$(az storage account keys list \
  --account-name $STORAGE_ACCOUNT \
  --resource-group $RESOURCE_GROUP \
  --query '[0].value' -o tsv)

az webapp config storage-account add \
  --resource-group $RESOURCE_GROUP \
  --name $APP_SERVICE_NAME \
  --custom-id fuel-storage \
  --storage-type AzureFiles \
  --account-name $STORAGE_ACCOUNT \
  --share-name fuel-data \
  --access-key $STORAGE_KEY \
  --mount-path /home/site/wwwroot/fuel_data
```

## Step 6: Verify Deployment

### 6.1 Check App Service Status
```bash
az webapp show \
  --resource-group $RESOURCE_GROUP \
  --name $APP_SERVICE_NAME \
  --query "defaultHostName" -o tsv
```

### 6.2 View Application Logs
```bash
az webapp log tail \
  --resource-group $RESOURCE_GROUP \
  --name $APP_SERVICE_NAME
```

### 6.3 Test Application
Open browser to: `https://<APP_SERVICE_NAME>.azurewebsites.net`

## Step 7: Continuous Integration/Continuous Deployment (CI/CD)

### Option A: GitHub Actions (Recommended)

Create `.github/workflows/deploy.yml`:

```yaml
name: Deploy to Azure App Service

on:
  push:
    branches: [ main ]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Login to Azure Container Registry
        uses: azure/docker-login@v1
        with:
          login-server: ${{ secrets.REGISTRY_NAME }}.azurecr.io
          username: ${{ secrets.REGISTRY_USERNAME }}
          password: ${{ secrets.REGISTRY_PASSWORD }}
      
      - name: Build and push image
        run: |
          docker build -t ${{ secrets.REGISTRY_NAME }}.azurecr.io/refuelingplatform:${{ github.sha }} .
          docker push ${{ secrets.REGISTRY_NAME }}.azurecr.io/refuelingplatform:${{ github.sha }}
      
      - name: Deploy to Azure App Service
        uses: azure/webapps-deploy@v2
        with:
          app-name: ${{ secrets.AZURE_APP_NAME }}
          publish-profile: ${{ secrets.AZURE_PUBLISH_PROFILE }}
          images: ${{ secrets.REGISTRY_NAME }}.azurecr.io/refuelingplatform:${{ github.sha }}
```

### Option B: Azure DevOps Pipeline

Create `azure-pipelines.yml` in repository root.

## Troubleshooting

### Issue: Application doesn't start
```bash
az webapp log tail --resource-group $RESOURCE_GROUP --name $APP_SERVICE_NAME
```

### Issue: Port binding error
Ensure `PORT` environment variable is set to 8000

### Issue: Out of memory
Consider upgrading App Service Plan (B2 → B3 or higher)

### Issue: Images not loading
Verify file permissions in `/home/site/wwwroot/fuel_data`

## Monitoring and Scaling

### Enable Application Insights
```bash
az monitor app-insights component create \
  --resource-group $RESOURCE_GROUP \
  --app refuelingplatform-insights

INSIGHTS_KEY=$(az monitor app-insights component show \
  --app refuelingplatform-insights \
  --resource-group $RESOURCE_GROUP \
  --query instrumentationKey -o tsv)

az webapp config appsettings set \
  --resource-group $RESOURCE_GROUP \
  --name $APP_SERVICE_NAME \
  --settings APPINSIGHTS_INSTRUMENTATIONKEY=$INSIGHTS_KEY
```

### Auto-scaling
```bash
az monitor autoscale-settings create \
  --resource-group $RESOURCE_GROUP \
  --resource-type "microsoft.web/serverfarms" \
  --resource-name $APP_SERVICE_PLAN \
  --name "autoscale" \
  --min-count 1 \
  --max-count 5 \
  --count 1
```

## Security Best Practices

1. **Enable HTTPS only**
```bash
az webapp update \
  --resource-group $RESOURCE_GROUP \
  --name $APP_SERVICE_NAME \
  --set httpsOnly=true
```

2. **Configure firewall rules** (if needed)
```bash
az webapp config access-restriction add \
  --resource-group $RESOURCE_GROUP \
  --name $APP_SERVICE_NAME \
  --rule-name "Allow VNet" \
  --action Allow \
  --priority 100 \
  --vnet-name <vnet-name> \
  --subnet <subnet-name>
```

3. **Use Key Vault for secrets**
```bash
az keyvault create \
  --name refuelingkeyvault \
  --resource-group $RESOURCE_GROUP
```

## Cost Optimization

- Use B1 plan for development/testing
- B2/B3 for production
- Enable auto-shutdown for dev resources
- Monitor resource usage regularly

## Next Steps

1. Configure database backend (Azure SQL/CosmosDB)
2. Setup backup and disaster recovery
3. Implement advanced monitoring
4. Configure custom domain name
5. Setup SSL certificate

## Support and Resources

- [Azure App Service Documentation](https://learn.microsoft.com/en-us/azure/app-service/)
- [Azure Container Registry](https://learn.microsoft.com/en-us/azure/container-registry/)
- [Gradio Deployment Guide](https://gradio.app/guides/hosting-your-app-with-hugging-face/)

- name: Upload deployment docs
  uses: actions/upload-artifact@v4
  with:
    name: deployment-docs
    path: azure-deployment.md
