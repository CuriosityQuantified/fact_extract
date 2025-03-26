#!/usr/bin/env python
"""
Script to create a sample Excel file with facts for testing.
"""

import pandas as pd
import os

def create_sample_facts():
    """Create a sample Excel file with facts for testing."""
    # Create sample facts
    facts = [
        {
            'document_name': 'climate_report.pdf',
            'chunk_index': 1,
            'statement': 'The global average surface temperature has increased by 1.1°C since the pre-industrial era.',
            'source_name': 'IPCC',
            'verification_status': 'verified'
        },
        {
            'document_name': 'energy_report.pdf',
            'chunk_index': 3,
            'statement': 'Renewable energy capacity increased by 45% worldwide between 2015 and 2020.',
            'source_name': 'IEA',
            'verification_status': 'verified'
        },
        {
            'document_name': 'ev_market_report.pdf',
            'chunk_index': 2,
            'statement': 'Electric vehicle sales grew by 65% in 2022 compared to the previous year.',
            'source_name': 'Bloomberg',
            'verification_status': 'verified'
        }
    ]

    # Create DataFrame and save to Excel
    df = pd.DataFrame(facts)
    os.makedirs('data', exist_ok=True)
    df.to_excel('data/all_facts.xlsx', index=False)
    print('Created sample facts Excel file with', len(facts), 'facts')

if __name__ == "__main__":
    create_sample_facts() 