# Pseudo-code structure
def automate_lawyer_enrichment():
    # 1. Get leads from Close CRM
    leads = close_api.get_leads(status="new")
    
    for lead in leads:
        # 2. Extract company/firm name from lead
        firm_name = extract_firm_name(lead)
        
        # 3. Skip if personal email detected
        if is_personal_email(lead.email):
            continue
            
        # 4. Search Apollo for the firm
        firm = apollo_api.search_companies(name=firm_name)
        
        if firm:
            # 5. Get employees from the firm
            employees = apollo_api.get_employees(
                company_id=firm.id,
                title_keywords=["attorney", "lawyer", "partner"]
            )
            
            # 6. Filter for verified emails and senior roles
            qualified_lawyers = filter_lawyers(employees)
            
            # 7. Create contacts in Close for each lawyer
            for lawyer in qualified_lawyers:
                close_api.create_contact(
                    lead_id=lead.id,
                    name=lawyer.name,
                    email=lawyer.email,
                    phone=lawyer.phone,
                    title=lawyer.title
                )