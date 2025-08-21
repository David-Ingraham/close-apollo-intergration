import json
with open('json/ai_recovery_test_results.json', 'r') as f:
    data = json.load(f)

total_leads = len(data['leads'])
ai_recovered = sum(1 for lead in data['leads'] if lead.get('ai_recovery'))
firm_classifications = sum(1 for lead in data['leads'] if lead.get('ai_recovery', {}).get('ai_classification') == 'FIRM')
person_classifications = sum(1 for lead in data['leads'] if lead.get('ai_recovery', {}).get('ai_classification') == 'PERSON')
junk_classifications = sum(1 for lead in data['leads'] if lead.get('ai_recovery', {}).get('ai_classification') == 'JUNK')

print(f'=== AI RECOVERY ANALYSIS ===')
print(f'Total leads in file: {total_leads}')
print(f'Leads with AI recovery: {ai_recovered}')
print(f'Classified as FIRM: {firm_classifications}')
print(f'Classified as PERSON: {person_classifications}')
print(f'Classified as JUNK: {junk_classifications}')
print(f'Success rate: {ai_recovered/total_leads*100:.1f}%')

if ai_recovered > 0:
    print(f'\n=== RECOVERED FIRM EXAMPLES ===')
    count = 0
    for lead in data['leads']:
        if lead.get('ai_recovery', {}).get('ai_classification') == 'FIRM':
            print(f'- {lead["attorney_firm"]} (confidence: {lead["ai_recovery"]["ai_confidence"]}/10)')
            count += 1
            if count >= 5:
                break