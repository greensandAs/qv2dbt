#!/bin/bash
# Local hosting quick-start for qv2dbt Studio
# Co-authored with CoCo

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== qv2dbt Studio — Local Setup ==="
echo ""

# Check Python version
python3 --version 2>/dev/null || { echo "ERROR: Python 3.11+ required"; exit 1; }

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt --quiet

# Create secrets template if not exists
if [ ! -f .streamlit/secrets.toml ]; then
    echo ""
    echo "Creating .streamlit/secrets.toml template..."
    cat > .streamlit/secrets.toml << 'EOF'
# Snowflake connection (optional — app works offline without it)
# Uncomment and fill in to enable Cortex AI and Run-in-Snowflake features.
#
# [connections.snowflake]
# account = "your_account"
# user = "your_user"
# password = "your_password"
# warehouse = "COMPUTE_WH"
# database = "YOUR_DB"
# schema = "PUBLIC"
# role = "YOUR_ROLE"
EOF
    echo "  Created .streamlit/secrets.toml (edit to add Snowflake credentials)"
fi

echo ""
echo "Starting qv2dbt Studio..."
echo "  URL: http://localhost:8501"
echo ""
streamlit run streamlit_app.py --server.port 8501 --server.maxUploadSize 50
