# ServiceNow AI Copilot

A modern, AI-powered ServiceNow instance analysis and optimization platform with an intuitive web interface.

## 🌟 Features

- **AI-Powered Analysis**: 8 specialized agents analyzing different aspects of your ServiceNow instance
- **Interactive Chat**: Real-time chat interface powered by LLM for instant insights
- **Modern UI**: Clean, responsive sidebar design built with Bootstrap 5
- **Comprehensive Reports**: Generate detailed PDF reports with all analysis results
- **Real-time Sync**: Background service continuously syncs data from ServiceNow
- **Multi-Agent Architecture**: Modular design with specialized agents for different analysis types

## 📋 Agents

1. **Architecture Agent** - Analyzes system architecture and configuration
2. **Scripts Agent** - Reviews custom scripts and business rules
3. **Performance Agent** - Monitors performance metrics and transactions
4. **Security Agent** - Audits security configurations and ACLs
5. **Integration Agent** - Examines REST APIs and integrations
6. **Data Health Agent** - Checks data quality and dictionary integrity
7. **Upgrade Agent** - Assesses upgrade readiness and compatibility
8. **License Optimization Agent** - Identifies unused licenses for cost savings

## 🚀 Quick Start

### Prerequisites

- Python 3.8 or higher
- MySQL Server (running on port 3307)
- Ollama with devstral-2:123b-cloud model (or modify in `ollama_client.py`)
- ServiceNow instance credentials

### Installation

1. **Extract the ZIP file**
   ```bash
   unzip servicenow-copilot.zip
   cd servicenow-copilot
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure MySQL Database**
   
   Update database credentials in `services/database.py`:
   ```python
   MYSQL_CONFIG = {
       "host": "127.0.0.1",
       "user": "root",
       "password": "your_password",
       "database": "sn_health",
       "port": 3307
   }
   ```

4. **Configure ServiceNow Connection**
   
   Update ServiceNow credentials in `services/servicenow_client.py`:
   ```python
   SN_INSTANCE = "https://your-instance.service-now.com"
   SN_USER = "your_username"
   SN_PASS = "your_password"
   ```

5. **Configure Ollama**
   
   Ensure Ollama is running and update the model in `ollama_client.py` if needed:
   ```python
   OLLAMA_URL = "http://localhost:11434/api/generate"
   MODEL = "devstral-2:123b-cloud"  # Change to your model
   ```

6. **Run the application**
   ```bash
   python -m uvicorn main:app --reload
   ```

7. **Access the dashboard**
   
   Open your browser and navigate to: http://127.0.0.1:8000/

## 📁 Project Structure

```
servicenow-copilot/
├── agents/                      # AI Agent modules
│   ├── __init__.py
│   ├── architecture.py
│   ├── scripts.py
│   ├── performance.py
│   ├── security.py
│   ├── integration.py
│   ├── data_health.py
│   ├── upgrade.py
│   └── license_optimization.py
├── services/                    # Backend services
│   ├── __init__.py
│   ├── database.py             # MySQL integration
│   ├── servicenow_client.py    # ServiceNow API client
│   └── sync_service.py         # Background sync service
├── static/                      # Frontend assets
│   ├── css/
│   │   └── style.css           # Custom styles
│   └── js/
│       └── app.js              # Frontend logic
├── templates/                   # HTML templates
│   └── index.html              # Main dashboard
├── main.py                      # FastAPI application
├── orchestrator.py             # Agent orchestrator
├── ollama_client.py            # LLM client
├── safety.py                   # Safety controls
└── requirements.txt            # Python dependencies
```

## 🎨 UI Features

### Sidebar Navigation
- **New Chat**: Start fresh conversation with AI assistant
- **ServiceNow Builder**: Access all 8 specialized agents
- **Actions**: Run all agents at once or generate reports

### Main Dashboard
- **Welcome Screen**: Overview of features and quick start guide
- **Interactive Chat**: Real-time conversation with AI copilot
- **Analysis Results**: Formatted JSON output with copy functionality
- **Loading States**: Visual feedback during agent execution

## 🔧 Configuration

### Safety Mode
Configure safety mode in `safety.py`:
- `observe`: Read-only mode (default)
- `suggest`: Provides recommendations
- `autonomous`: Executes changes automatically

### Sync Interval
Modify sync interval in `services/sync_service.py`:
```python
time.sleep(30)  # Sync every 30 seconds
```

### Tables to Sync
Add or remove tables in `services/sync_service.py`:
```python
TABLES = [
    "sys_db_object",
    "sys_script",
    "syslog_transaction",
    # Add more tables as needed
]
```

## 📊 API Endpoints

### Agent Endpoints
- `GET /agent/architecture` - Run architecture analysis
- `GET /agent/scripts` - Run scripts analysis
- `GET /agent/performance` - Run performance analysis
- `GET /agent/security` - Run security analysis
- `GET /agent/integration` - Run integration analysis
- `GET /agent/data-health` - Run data health analysis
- `GET /agent/upgrade` - Run upgrade analysis
- `GET /agent/license-optimization` - Run license optimization

### Action Endpoints
- `GET /run-all` - Execute all agents
- `GET /generate-report` - Download PDF report
- `POST /chat` - Interactive chat endpoint
- `GET /health` - Health check

### API Documentation
Full interactive API documentation available at: http://127.0.0.1:8000/docs

## 🛠️ Development

### Running in Development Mode
```bash
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Testing Individual Agents
```python
from agents import architecture
result = architecture.run()
print(result)
```

### Adding New Agents
1. Create new file in `agents/` directory
2. Implement `run()` function
3. Add import to `agents/__init__.py`
4. Add route in `main.py`
5. Add button in `templates/index.html`

## 📝 Troubleshooting

### Database Connection Issues
- Ensure MySQL is running on port 3307
- Verify credentials in `services/database.py`
- Check database exists: `CREATE DATABASE IF NOT EXISTS sn_health;`

### ServiceNow API Issues
- Verify instance URL (no trailing slash)
- Check credentials and permissions
- Ensure API access is enabled for your user

### Ollama Connection Issues
- Verify Ollama is running: `ollama list`
- Check the model is available: `ollama pull devstral-2:123b-cloud`
- Test connection: `curl http://localhost:11434/api/generate`

### Static Files Not Loading
- Ensure `static/` directory exists with `css/` and `js/` subdirectories
- Check file permissions
- Clear browser cache

## 🔐 Security Notes

- Change default ServiceNow credentials in `servicenow_client.py`
- Use environment variables for sensitive data in production
- Enable authentication for production deployments
- Review and customize safety mode settings

## 📄 License

This project is provided as-is for ServiceNow instance analysis and optimization.

## 🤝 Support

For issues or questions:
1. Check the troubleshooting section
2. Review API documentation at `/docs`
3. Examine browser console for frontend errors
4. Check terminal logs for backend errors

## 🎯 Roadmap

- [ ] User authentication and authorization
- [ ] Multi-instance support
- [ ] Scheduled analysis reports
- [ ] Email notifications
- [ ] Custom agent creation UI
- [ ] Historical trend analysis
- [ ] Export to multiple formats (CSV, Excel)

---

**Version**: 2.0  
**Last Updated**: 2024

Happy analyzing! 🚀
