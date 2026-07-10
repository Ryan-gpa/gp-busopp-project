import os
res = {
    "ENVIRONMENT": os.environ.get("ENVIRONMENT"),
    "RAILWAY_ENVIRONMENT": os.environ.get("RAILWAY_ENVIRONMENT"),
    "RAILWAY_VOLUME_MOUNT_PATH": os.environ.get("RAILWAY_VOLUME_MOUNT_PATH"),
    "DATA_DIR": os.environ.get("DATA_DIR")
}
print(res)
