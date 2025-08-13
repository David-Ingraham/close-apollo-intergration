# Close Apollo Integration

A comprehensive system for enriching Close CRM leads with lawyer contact information from Apollo.io. This system identifies law firms from Close CRM leads, finds additional attorneys at those firms, unlocks their email addresses, and requests phone numbers via webhook.

## System Overview

This integration connects Close CRM with Apollo.io to:
1. Extract leads from Close CRM that represent potential clients
2. Identify the law firms representing these clients
3. Find additional attorneys at those law firms
4. Unlock email addresses for relevant contacts
5. Request phone numbers asynchronously via webhook
6. Update Close CRM with the enriched contact data

## Core Scripts and Execution Flow

### 1. Lead Data Extraction
**Script:** `get_lawyer_contacts.py`
- **Purpose:** Retrieves leads from Close CRM and extracts attorney/firm information
- **Reads:** Close CRM API via smart views
- **Writes:** Structured lead data for processing
- **Key Functions:**
  - Connects to Close CRM using saved search views
  - Extracts client information and attorney details from custom fields
  - Determines which leads need Apollo enrichment

### 2. Master Orchestration
**Script:** `master_orchestration.py` (Primary execution script)
- **Purpose:** Coordinates the entire enrichment pipeline
- **Execution:** `python master_orchestration.py`
- **Modes:**
  - **Testing Mode:** Runs enrichment but stops before phone requests (no Apollo credits consumed)
  - **Production Mode:** Full pipeline including phone requests and Close CRM updates
- **Flow:**
  1. Gets leads data from Close CRM
  2. Runs Apollo company and people enrichment
  3. Saves comprehensive results to timestamped files
  4. In production mode: sends phone requests and updates Close CRM

### 3. Apollo Company Enrichment
**Script:** `apollo_enrich.py`
- **Purpose:** Core Apollo integration for company and people search
- **Key Functions:**
  - `search_firm_with_retry()`: Finds law firms in Apollo based on lead data
  - `choose_best_org()`: Applies sophisticated matching logic to select correct firm
  - `search_people_at_organization()`: Finds lawyers at identified firms
- **Filtering Logic:** Uses industry classification, name similarity, and domain validation

### 4. Webhook Server
**Script:** `webhook_server.py`
- **Purpose:** Receives asynchronous phone number data from Apollo
- **Execution:** Run before starting pipeline: `python webhook_server.py`
- **Endpoints:**
  - `POST /apollo-webhook`: Receives phone data
  - `GET /webhook-health`: Health monitoring
  - `GET /webhook-data`: View received data
- **Writes:** 
  - `webhook_data.json`: Current session data
  - `apollo_num_response.{timestamp}.json`: Individual webhook responses

### 5. Phone Number Requests
**Script:** `get_apollo_nums.py`
- **Purpose:** Sends asynchronous phone enrichment requests to Apollo
- **Execution:** Called automatically by master orchestration in production mode
- **Process:** Submits requests for phone numbers that arrive via webhook 5-30 minutes later

### 6. Close CRM Updates
**Script:** `update_close_leads.py`
- **Purpose:** Updates Close CRM with enriched contact data
- **Execution:** Called automatically by master orchestration
- **Updates:** Adds attorney emails and phone numbers to lead records

## File Management System

### Directory Structure
```
project_root/
├── data/
│   ├── results/           # Enrichment results (7-day retention)
│   ├── logs/             # Application logs (7-day retention)
│   ├── webhooks/         # Apollo webhook responses (7-day retention)
│   └── temp/             # Temporary files (1-day retention)
├── config/               # Configuration files
└── deploy/               # Deployment scripts
```

### File Naming Conventions
- **Results:** `enrichment_results_{timestamp}.json`
- **Webhook logs:** `apollo_webhook_{timestamp}.json`
- **Application logs:** `{script_name}_{date}.log`
- **Timestamped responses:** `apollo_num_response.{timestamp}_{unix}.json`

### Automatic Cleanup
**Script:** `file_manager.py`
- **Execution:** `python file_manager.py cleanup`
- **Schedule:** Daily via cron at 2 AM
- **Retention:** 7 days for results/logs/webhooks, 1 day for temporary files

## Lead Filtering Process

### Primary Filtering Criteria

#### 1. Firm Name Validation
- **Required:** Lead must have a law firm email and not personal
- **Sources:** Multiple custom field mappings for firm names. Email domain prioritized, the Law office, then attorney name (could be filled by lead as name of lawyer or name of firm)


#### 2. Email Domain Analysis
- **Personal Domains:** Gmail, Yahoo, Hotmail, etc. are flagged
- **Cross-Reference:** Domain must match attoney email given by lead

#### 3. Search Strategy Determination
The system determines search approach based on available data:
- **Domain Strategy:** When attorney has professional email domain
- **Name Strategy:** When only firm name is available
- **Skip Decision:** When neither reliable identifier exists

#### 4. Industry Classification
**Function:** `is_law_firm_by_industry()`
- **Keywords:** Legal, law, attorney, lawyer, counsel, court, litigation
- **Industry Codes:** Apollo industry classifications for legal services
- **Validation:** Ensures Apollo results are actually law firms

### Firm Matching Algorithm

#### Scoring System
The `calculate_firm_match_score()` function evaluates candidates using:

1. **Name Similarity (60% weight)**
   - Fuzzy string matching between lead firm name and Apollo organization
   - Handles variations like "Smith & Associates" vs "Smith Associates"

2. **Core Coverage (30% weight)**
   - Ensures key terms from lead firm name appear in candidate
   - Prevents false matches with completely different firms

3. **Bonus Factors (10% weight)**
   - Domain presence and validity
   - LinkedIn profile existence
   - Word token matching

#### Confidence Thresholds
- **High Confidence:** 95% similarity required when no email validation possible
- **Domain Validated:** 60% similarity acceptable with matching email domain
- **Standard:** 75% similarity for other cases

#### Multi-Candidate Resolution
When multiple firms match:
- Exact domain matches take priority
- Industry filtering eliminates non-law firms
- Similarity scores determine best candidate
- Ambiguous matches are rejected to prevent false positives

## Email Unlock Process

### Target Identification
The system identifies contacts for email unlocking based on:

#### 1. Title Prioritization
**Function:** `prioritize_by_legal_titles()`
- **Tier 1:** Partner, Managing Partner, Senior Partner
- **Tier 2:** Associate, Senior Associate, Of Counsel
- **Tier 3:** Attorney, Lawyer, Counsel
- **Tier 4:** Other legal professionals

#### 2. Contact Limits
- **Target:** 6 contacts per firm maximum
- **Rationale:** Balances comprehensiveness with Apollo credit costs
- **Distribution:** Prioritizes senior roles, ensures variety

#### 3. Domain Validation
**Process:** Before unlocking emails, the system:
- Extracts domain from any unlocked email
- Compares against expected firm domain
- Rejects contacts with non-matching domains
- Prevents credits spent on incorrect contacts

### Email Unlock Execution
**Function:** `search_people_at_organization()`

#### Step 1: People Search
- Queries Apollo for all people at identified organization
- Filters by legal titles and seniority
- Sorts by relevance and title priority

#### Step 2: Credit-Conscious Unlocking
- Performs email unlock requests for priority contacts
- Validates domain match before accepting results
- Stops when target contact count reached
- Implements rate limiting to respect API limits

#### Step 3: Quality Control
- Verifies email format and deliverability indicators
- Ensures contact diversity across seniority levels
- Logs successful unlocks and credit usage

### Email Unlock Criteria Summary
**Who gets emails unlocked:**
- Attorneys and lawyers at validated law firms
- Contacts with priority legal titles
- Maximum 6 contacts per firm
- Domain-validated email addresses only

**Why these criteria:**
- **Cost Control:** Limits Apollo credit usage to relevant contacts
- **Quality Assurance:** Ensures emails belong to target law firm
- **Relevance:** Focuses on decision-makers and case handlers
- **Efficiency:** Balances thorough coverage with resource constraints

## Phone Number Process

### Asynchronous Workflow
Phone numbers are obtained through Apollo's webhook system:

#### 1. Request Submission
**Script:** `get_apollo_nums.py`
- Submits phone enrichment requests for email-unlocked contacts
- Includes webhook URL for response delivery
- Processes requests in batches with rate limiting

#### 2. Webhook Reception
**Script:** `webhook_server.py`
- Receives phone data 5-30 minutes after request
- Validates and logs incoming webhook data
- Stores responses for later processing

#### 3. Data Integration
The master orchestration waits for webhook responses and:
- Matches phone data to original contacts
- Updates comprehensive results files
- Prepares data for Close CRM integration

## Close CRM Integration

### Update Process
**Script:** `update_close_leads.py`
- Reads enriched contact data from results files
- Matches contacts to original leads in Close CRM
- Updates lead records with attorney emails and phone numbers
- Handles duplicate detection and data validation

### Data Mapping
- **Email Fields:** Maps to attorney email custom fields
- **Phone Fields:** Updates contact phone number fields
- **Firm Information:** Enhances firm name and domain data
- **Notes:** Adds enrichment metadata and timestamps

## Prerequisites and Setup

### Environment Variables
Create `.env` file with:
```
CLOSE_API_KEY=your_close_api_key_here
APOLLO_API_KEY=your_apollo_api_key_here
WEBHOOK_URL=your_ngrok_or_server_url
```

### Required Packages
```
pip install -r requirements.txt
```

### Webhook Server Setup
1. Start webhook server: `python webhook_server.py`
2. Start ngrok tunnel: `ngrok http 5000`
3. Update WEBHOOK_URL in `.env` with ngrok URL

## Execution Instructions

### Testing Mode (Recommended First Run)
```bash
python master_orchestration.py
# Select option 1 for Testing Mode
```
- Runs complete pipeline except phone requests
- No Apollo credits consumed
- Generates results file for review
- Allows verification before production run

### Production Mode
```bash
python master_orchestration.py
# Select option 2 for Production Mode
```
- Runs complete pipeline including phone requests
- Consumes Apollo credits for email unlocking and phone requests
- Updates Close CRM with enriched data
- Requires webhook server to be running

### Manual Script Execution
Individual scripts can be run for testing:
```bash
python get_lawyer_contacts.py    # Test lead extraction
python apollo_enrich.py         # Test firm search
python webhook_server.py        # Start webhook receiver
python get_apollo_nums.py       # Send phone requests
python update_close_leads.py    # Update Close CRM
```

## Output Files and Data Flow

### Results Files
**Primary Output:** `enrichment_results_{timestamp}.json`
- Complete pipeline results with metadata
- Lead data, Apollo search results, enriched contacts
- Success rates and processing statistics
- Used for Close CRM updates and analysis

### Logging Files
- **Pipeline logs:** Track execution progress and errors
- **API logs:** Record Apollo and Close CRM interactions
- **Webhook logs:** Individual phone number responses
- **Debug logs:** Detailed execution information for troubleshooting

### Data Persistence
- All files include metadata with retention policies
- Automatic cleanup prevents disk space issues
- Timestamped files enable historical analysis
- Structured JSON format for programmatic access

## Error Handling and Recovery

### Retry Logic
- Apollo API requests include exponential backoff
- Close CRM operations retry on temporary failures
- Network timeouts are handled gracefully

### Validation Checkpoints
- Lead data validation before processing
- Apollo response validation before acceptance
- Close CRM update validation with rollback capability

### Logging and Monitoring
- Comprehensive error logging with stack traces
- Success/failure metrics for each pipeline stage
- Webhook health monitoring and alerts

This system provides a robust, automated solution for enriching Close CRM leads with comprehensive law firm contact information while maintaining cost control and data quality.

