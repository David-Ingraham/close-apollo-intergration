import json

def test_contact_flattening():
    """Test the contact flattening logic with sample data"""
    
    # Sample data structure that mimics the Apollo enrichment results
    sample_data = {
        'search_results': [
            {
                'search_successful': True,
                'client_name': 'John Doe',
                'firm_name': 'Test Law Firm',
                'contacts': [
                    # Individual contact dict (good)
                    {'name': 'Attorney One', 'email': 'attorney1@firm.com', 'title': 'Partner'},
                    
                    # List of contacts (problematic)
                    [
                        {'name': 'Attorney Two', 'email': 'attorney2@firm.com', 'title': 'Associate'},
                        {'name': 'Attorney Three', 'email': 'attorney3@firm.com', 'title': 'Paralegal'}
                    ],
                    
                    # String placeholder (problematic)
                    'fallback_org_1',
                    
                    # Another individual contact (good)
                    {'name': 'Attorney Four', 'email': 'attorney4@firm.com', 'title': 'Of Counsel'}
                ]
            }
        ]
    }
    
    print("ORIGINAL DATA STRUCTURE:")
    print("========================")
    for result in sample_data['search_results']:
        if result.get('search_successful'):
            contacts = result.get('contacts', [])
            print(f"Raw contacts count: {len(contacts)}")
            for i, contact in enumerate(contacts):
                print(f"  contacts[{i}]: {type(contact)} - {contact}")
    
    print("\nFLATTENED DATA STRUCTURE:")
    print("=========================")
    
    # Test the flattening logic
    for result in sample_data['search_results']:
        if result.get('search_successful'):
            raw_contacts = result.get('contacts', [])
            
            # Flatten contacts
            flattened_contacts = []
            for contact in raw_contacts:
                if isinstance(contact, dict):
                    # Individual contact dictionary
                    flattened_contacts.append(contact)
                elif isinstance(contact, list):
                    # List of contacts - flatten it
                    for sub_contact in contact:
                        if isinstance(sub_contact, dict):
                            flattened_contacts.append(sub_contact)
                # Skip strings or other invalid types
            
            print(f"Flattened contacts count: {len(flattened_contacts)}")
            for i, contact in enumerate(flattened_contacts):
                print(f"  flattened[{i}]: {type(contact)} - {contact}")
    
    print("\nTEST LINE 92 LOGIC:")
    print("===================")
    
    # Test the problematic line 92 logic before fix
    try:
        count_before = sum(1 for firm in sample_data['search_results'] 
                          if firm.get('search_successful') 
                          for contact in firm.get('contacts', []) 
                          if contact.get('email'))
        print(f"Count with original logic: {count_before}")
    except AttributeError as e:
        print(f"ERROR with original logic: {e}")
    
    # Test the fixed line 92 logic
    def count_contacts_with_emails(data):
        count = 0
        for firm in data['search_results']:
            if firm.get('search_successful'):
                raw_contacts = firm.get('contacts', [])
                
                # Flatten contacts first
                flattened_contacts = []
                for contact in raw_contacts:
                    if isinstance(contact, dict):
                        flattened_contacts.append(contact)
                    elif isinstance(contact, list):
                        for sub_contact in contact:
                            if isinstance(sub_contact, dict):
                                flattened_contacts.append(sub_contact)
                
                # Count contacts with emails
                count += sum(1 for contact in flattened_contacts if contact.get('email'))
        return count
    
    count_after = count_contacts_with_emails(sample_data)
    print(f"Count with fixed logic: {count_after}")

if __name__ == "__main__":
    test_contact_flattening() 