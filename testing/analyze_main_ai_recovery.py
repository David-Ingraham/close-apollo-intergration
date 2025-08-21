import json

# Load the main skipped leads file from your 536 lead run
with open('json/all_leads_skipped_2025-08-19_14-56-18.json', 'r') as f:
    skipped_data = json.load(f)

print(f'=== AI RECOVERY ANALYSIS - 536 LEAD RUN (Aug 19) ===')
print(f'Total skipped leads: {len(skipped_data)}')

# Count different skip reasons
skip_reasons = {}
ai_processed = 0
ai_recovered_firms = 0
ai_recovered_persons = 0
ai_recovered_junk = 0

for lead in skipped_data:
    reason = lead.get('skip_reason', 'unknown')
    skip_reasons[reason] = skip_reasons.get(reason, 0) + 1
    
    # Check if this lead was processed by AI
    if 'ai_recovery' in lead:
        ai_processed += 1
        classification = lead['ai_recovery'].get('ai_classification')
        if classification == 'FIRM':
            ai_recovered_firms += 1
        elif classification == 'PERSON':
            ai_recovered_persons += 1
        elif classification == 'JUNK':
            ai_recovered_junk += 1

print(f'\n=== SKIP REASONS BREAKDOWN ===')
for reason, count in sorted(skip_reasons.items(), key=lambda x: x[1], reverse=True):
    print(f'{reason}: {count} leads')

print(f'\n=== AI RECOVERY RESULTS ===')
print(f'Leads processed by AI: {ai_processed}')
print(f'Classified as FIRM: {ai_recovered_firms}')
print(f'Classified as PERSON: {ai_recovered_persons}')
print(f'Classified as JUNK: {ai_recovered_junk}')

if ai_processed > 0:
    success_rate = (ai_recovered_firms / ai_processed) * 100
    print(f'AI Recovery Success Rate: {success_rate:.1f}% (firms recovered)')

# Show examples of recovered firms
print(f'\n=== RECOVERED FIRM EXAMPLES ===')
count = 0
for lead in skipped_data:
    if lead.get('ai_recovery', {}).get('ai_classification') == 'FIRM':
        firm_name = lead.get('attorney_name', 'Unknown')
        confidence = lead['ai_recovery'].get('ai_confidence', 0)
        website = lead.get('firm_website', 'No website')
        print(f'- {firm_name} (confidence: {confidence}/10) - {website}')
        count += 1
        if count >= 10:
            print(f'... and {ai_recovered_firms - 10} more')
            break
