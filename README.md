

```markdown
# Apollo-Close Integration Pipeline

A fully automated system that enriches Close CRM leads with attorney contact information from Apollo.io, including verified phone numbers and email addresses.

## System Overview

This pipeline automatically:
1. Extracts leads from Close CRM "Today's Leads" view
2. Searches Apollo.io for law firms matching each lead's attorney
3. Retrieves all attorneys and staff from matched firms
4. Enriches contact data with verified phone numbers via Apollo webhooks
5. Stores enriched data for CRM import

## Architecture

### Local Development
```
Close CRM API → apollo_enrich.py → Apollo.io API
                      ↓
              apollo_company_results.json
                      ↓
              webhook_server.py ← Apollo.io webhooks
                      ↓
              Final enriched data
```

### AWS Production (Planned)
```
EventBridge (daily) → Daily Lambda → Apollo.io API
                           ↓
Apollo webhooks → API Gateway → Webhook Lambda → S3 results
```

## Prerequisites

### API Accounts Required
1. **Close CRM API Access**
   - Account with API permissions
   - Smart View access to "Today's Leads"

2. **Apollo.io API Access**
   - Paid account with API credits
   - Phone number reveal credits
   - Webhook capabilities

3. **Development Tools**
   - Python 3.9+
   - ngrok account (for local webhook testing)

### Environment Variables
Create a `.env` file with:
```
CLOSE_API_KEY=your_close_api_key_here
APOLLO_API_KEY=your_apollo_api_key_here
NGROK_URL=https://your-ngrok-url.ngrok-free.app
```

## Installation

### 1. Clone and Setup
```bash
git clone <repository-url>
cd close_apollo_integration
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Install ngrok
```bash
# Download from https://ngrok.com/download
# Or via package manager:
# Windows: choco install ngrok
# macOS: brew install ngrok
```

## File Structure

```
close_apollo_integration/
├── apollo_enrich.py              # Main enrichment pipeline
├── get_lawyer_contacts.py        # Close CRM lead extraction
├── webhook_server.py             # Local webhook receiver
├── test_webhook.py               # Webhook testing utilities
├── requirements.txt              # Python dependencies
├── lawyers_of_lead_poor.json     # Extracted leads from Close
├── apollo_company_results.json   # Company and people search results
├── apollo_search_results.json    # Raw Apollo search responses
├── logs/
│   ├── model_context.txt         # Project context documentation
│   └── debug_output.txt          # Debug logs
└── testing/
    ├── test_apollo_api.py        # Apollo API integration tests
    ├── test_close_api.py         # Close API integration tests
    └── test_people_enrichment.py # People enrichment tests
```

## Usage

### Step 1: Extract Leads from Close CRM
```bash
python get_lawyer_contacts.py
```
**Output:** `lawyers_of_lead_poor.json` containing leads with attorney information

### Step 2: Company and People Enrichment
```bash
python apollo_enrich.py
```
**Process:**
- Searches Apollo for law firms matching attorney names
- Uses multiple search strategies (exact name, variations, domain-based)
- Ranks and selects best company matches
- Retrieves all attorneys and staff from selected firms
- Filters for legal professionals (attorneys, partners, paralegals)

**Output:** `apollo_company_results.json` with company and people data

### Step 3: Phone Number Enrichment (Local Testing)

#### Terminal 1: Start Webhook Server
```bash
python webhook_server.py
```

#### Terminal 2: Start ngrok Tunnel
```bash
ngrok http 5000
```
Copy the HTTPS URL to your `.env` file as `NGROK_URL`

#### Terminal 3: Test Webhook Integration
```bash
python test_webhook.py
```

**Process:**
- Validates webhook server connectivity
- Sends phone enrichment requests to Apollo
- Apollo processes requests asynchronously (5-30 minutes)
- Phone data delivered to webhook server
- Results saved to `webhook_data.json`

## Data Flow Details

### 1. Lead Extraction (`get_lawyer_contacts.py`)
- Connects to Close CRM API
- Queries "Today's Leads" Smart View
- Extracts client and attorney information
- Normalizes firm names and contact data

### 2. Company Search (`apollo_enrich.py`)
**Search Strategies (in order):**
1. Exact firm name match
2. Quoted firm name search
3. Individual word searches
4. Normalized variations ("&" → "and", etc.)
5. Domain-based fallback searches
6. Domain root matching

**Scoring Algorithm:**
- Text similarity (difflib)
- Token coverage
- Legal keyword presence
- Domain matching bonuses
- Acronym matching

### 3. People Search
**Filters:**
- Job titles: attorney, partner, lawyer, counsel, paralegal
- Active employment status
- Minimum confidence thresholds

**Data Retrieved:**
- Full name and title
- Email addresses (with verification status)
- LinkedIn profiles
- Company affiliation

### 4. Phone Enrichment
**Webhook Process:**
1. Send enrichment request with person ID and webhook URL
2. Apollo queues phone number lookup
3. Apollo sends results to webhook (5-30 minutes later)
4. Webhook server receives and stores phone data
5. Data includes multiple numbers with confidence scores

## Configuration

### Search Parameters
```python
# apollo_enrich.py line ~306
"person_titles": ["attorney", "partner", "lawyer", "counsel", "paralegal"]

# Scoring thresholds (line ~245)
SIMILARITY_THRESHOLD = 0.15  # Minimum acceptance score
AMBIGUITY_THRESHOLD = 0.05   # Minimum gap between top 2 results
```

### Webhook Settings
```python
# webhook_server.py
PORT = 5000
WEBHOOK_ENDPOINT = "/apollo-webhook"
HEALTH_CHECK_ENDPOINT = "/webhook-health"
```

## API Endpoints and Costs

### Apollo.io API Calls
- **Company Search:** `POST /v1/mixed_companies/search` (1 credit per search)
- **People Search:** `POST /v1/mixed_people/search` (1 credit per search)
- **Phone Enrichment:** `POST /v1/people/match` (5 credits per phone reveal)

### Close CRM API Calls
- **Lead Search:** `POST /api/v1/data/search/` (free within plan limits)

## Error Handling

### Common Issues
1. **No Apollo Results:** Firm name variations not found
   - Check manual Apollo search with same terms
   - Verify firm still exists/active
   - Try alternative name formats

2. **Webhook Timeout:** Phone data not received
   - Check ngrok tunnel status
   - Verify webhook URL in Apollo dashboard
   - Apollo processing can take up to 30 minutes

3. **API Rate Limits:** Too many requests
   - Apollo: Built-in rate limiting in code
   - Close: Respect plan limits

### Debug Logging
All scripts include detailed console logging:
- Search attempts and results
- Scoring breakdowns
- API response summaries
- Error details with suggestions

## AWS Deployment (Planned)

### Infrastructure
- **EventBridge:** Daily trigger at 9 AM EST
- **Lambda Functions:** 
  - Daily enrichment pipeline
  - Webhook response handler
- **API Gateway:** Permanent webhook endpoint
- **S3:** Results storage
- **CloudWatch:** Logging and monitoring

### Estimated Costs
- **Monthly:** $0.00 - $1.00 (within AWS free tier)
- **Apollo Credits:** ~$50-100/month (depending on volume)

## Testing

### Unit Tests
```bash
python testing/test_apollo_api.py     # Apollo API connectivity
python testing/test_close_api.py      # Close API connectivity
python testing/test_people_enrichment.py  # End-to-end people flow
```

### Integration Testing
```bash
python test_webhook.py  # Full webhook pipeline test
```

## Data Security

### API Keys
- Stored in `.env` file (not committed to git)
- Use environment variables in production
- Rotate keys regularly

### Data Handling
- All PII processed locally or in secure AWS environment
- No persistent storage of sensitive data beyond 24 hours
- Webhook data automatically purged after processing

## Monitoring and Maintenance

### Success Metrics
- **Company Match Rate:** Target >80% successful firm matches
- **People Discovery:** Average 3-5 attorneys per firm
- **Phone Enrichment:** Target >60% successful phone reveals

### Daily Checks
- Review `apollo_company_results.json` for match quality
- Monitor Apollo credit consumption
- Check webhook delivery success rates

### Monthly Tasks
- Audit API key security
- Review and optimize search algorithms
- Update legal title keywords as needed

## Troubleshooting

### Apollo Search Issues
**Symptom:** Good firms not found in API but visible in Apollo dashboard
**Solutions:**
1. Check endpoint differences (UI vs API)
2. Try exact quoted searches
3. Use domain-based fallback searches
4. Verify firm name normalization

### Webhook Issues
**Symptom:** Phone data requests sent but no webhook responses
**Solutions:**
1. Verify ngrok tunnel active and public
2. Check Apollo webhook configuration
3. Confirm webhook URL format includes protocol (https://)
4. Test webhook with mock data first

### Performance Issues
**Symptom:** Script runs slowly or times out
**Solutions:**
1. Reduce batch sizes for API calls
2. Implement request throttling
3. Use parallel processing for independent operations
4. Cache successful company matches

## Contributing

### Code Style
- Follow PEP 8 formatting
- Include docstrings for all functions
- Add type hints where appropriate
- No emojis in code or output

### Testing
- Test all API integrations before deployment
- Verify webhook functionality with real Apollo data
- Document any new environment variables or dependencies

## License

[Your license here]

## Support

For issues or questions:
1. Check logs in `logs/debug_output.txt`
2. Review API documentation for Apollo and Close
3. Test individual components in isolation
4. Contact system administrator
```

This README provides comprehensive documentation covering installation, usage, architecture, troubleshooting, and deployment details for your Apollo-Close integration pipeline.