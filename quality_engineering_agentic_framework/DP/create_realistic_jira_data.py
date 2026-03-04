"""
Enhanced JIRA Data Generator - 5000 Records
Generates both SPRINT and STORY level data with RCA and code segments
"""
import pandas as pd
import numpy as np
import random
from datetime import datetime, timedelta

random.seed(42)
np.random.seed(42)

# ══════════════════════════════════════════════════════════════
# CONFIGURATION
# ══════════════════════════════════════════════════════════════
NUM_SPRINT_RECORDS = 5000
NUM_STORY_RECORDS = 5000

COMPONENTS = [
    'Billing & Invoicing', 'Payment Gateway', 'User Authentication',
    'API Gateway', 'Frontend Dashboard', 'Reporting Module',
    'Email Service', 'Database Layer', 'Mobile App - iOS',
    'Mobile App - Android', 'Integration Hub', 'Admin Portal',
    'Search Engine', 'Data Warehouse'
]

RISK_PROFILES = {
    'Billing & Invoicing':    'high',
    'Payment Gateway':        'critical',
    'User Authentication':    'high',
    'API Gateway':            'medium',
    'Frontend Dashboard':     'medium',
    'Reporting Module':       'low',
    'Email Service':          'low',
    'Database Layer':         'high',
    'Mobile App - iOS':       'medium',
    'Mobile App - Android':   'medium',
    'Integration Hub':        'high',
    'Admin Portal':           'low',
    'Search Engine':          'medium',
    'Data Warehouse':         'high'
}

# RCA categories with realistic distributions per component
RCA_CATEGORIES = {
    'Billing & Invoicing': [
        ('Inadequate unit testing', 0.30),
        ('Complex business logic error', 0.25),
        ('Integration failure', 0.20),
        ('Data validation missing', 0.15),
        ('Race condition', 0.10)
    ],
    'Payment Gateway': [
        ('Integration failure', 0.35),
        ('Security vulnerability', 0.25),
        ('Race condition', 0.20),
        ('Data validation missing', 0.15),
        ('Inadequate unit testing', 0.05)
    ],
    'User Authentication': [
        ('Security vulnerability', 0.40),
        ('Race condition', 0.25),
        ('Integration failure', 0.20),
        ('Inadequate unit testing', 0.15)
    ],
    'API Gateway': [
        ('Integration failure', 0.40),
        ('Inadequate unit testing', 0.25),
        ('Race condition', 0.20),
        ('Data validation missing', 0.15)
    ],
    'Frontend Dashboard': [
        ('Inadequate unit testing', 0.35),
        ('UI/UX logic error', 0.30),
        ('Integration failure', 0.20),
        ('Data validation missing', 0.15)
    ],
    'Reporting Module': [
        ('Data validation missing', 0.35),
        ('Complex business logic error', 0.30),
        ('Inadequate unit testing', 0.25),
        ('Integration failure', 0.10)
    ],
    'Email Service': [
        ('Integration failure', 0.40),
        ('Inadequate unit testing', 0.35),
        ('Data validation missing', 0.25)
    ],
    'Database Layer': [
        ('Race condition', 0.35),
        ('Complex business logic error', 0.25),
        ('Data validation missing', 0.25),
        ('Inadequate unit testing', 0.15)
    ],
    'Mobile App - iOS': [
        ('UI/UX logic error', 0.30),
        ('Inadequate unit testing', 0.30),
        ('Integration failure', 0.25),
        ('Race condition', 0.15)
    ],
    'Mobile App - Android': [
        ('UI/UX logic error', 0.30),
        ('Inadequate unit testing', 0.30),
        ('Integration failure', 0.25),
        ('Race condition', 0.15)
    ],
    'Integration Hub': [
        ('Integration failure', 0.45),
        ('Race condition', 0.25),
        ('Data validation missing', 0.20),
        ('Inadequate unit testing', 0.10)
    ],
    'Admin Portal': [
        ('Inadequate unit testing', 0.40),
        ('UI/UX logic error', 0.30),
        ('Data validation missing', 0.30)
    ],
    'Search Engine': [
        ('Complex business logic error', 0.35),
        ('Race condition', 0.30),
        ('Inadequate unit testing', 0.25),
        ('Integration failure', 0.10)
    ],
    'Data Warehouse': [
        ('Data validation missing', 0.35),
        ('Race condition', 0.30),
        ('Complex business logic error', 0.25),
        ('Inadequate unit testing', 0.10)
    ]
}

# Code files per component (realistic)
CODE_SEGMENTS = {
    'Billing & Invoicing': [
        'InvoiceGenerator.java', 'BillingService.java',
        'PaymentCalculator.java', 'TaxProcessor.java',
        'InvoiceRepository.java', 'BillingController.java'
    ],
    'Payment Gateway': [
        'PaymentProcessor.java', 'GatewayConnector.java',
        'TransactionManager.java', 'RefundService.java',
        'PaymentValidator.java', 'FraudDetector.java'
    ],
    'User Authentication': [
        'AuthService.java', 'TokenManager.java',
        'PasswordEncoder.java', 'SessionHandler.java',
        'OAuthConnector.java', 'UserValidator.java'
    ],
    'API Gateway': [
        'RouteHandler.java', 'RequestFilter.java',
        'RateLimiter.java', 'ApiController.java',
        'ResponseMapper.java', 'AuthMiddleware.java'
    ],
    'Frontend Dashboard': [
        'DashboardComponent.tsx', 'ChartRenderer.tsx',
        'DataFetcher.ts', 'FilterPanel.tsx',
        'ExportHandler.ts', 'StateManager.ts'
    ],
    'Reporting Module': [
        'ReportGenerator.java', 'DataAggregator.java',
        'ExportService.java', 'ReportScheduler.java',
        'MetricsCalculator.java', 'ReportRepository.java'
    ],
    'Email Service': [
        'EmailSender.java', 'TemplateEngine.java',
        'QueueManager.java', 'AttachmentHandler.java',
        'EmailValidator.java', 'RetryService.java'
    ],
    'Database Layer': [
        'ConnectionPool.java', 'QueryOptimizer.java',
        'TransactionHandler.java', 'MigrationService.java',
        'CacheManager.java', 'DatabaseRouter.java'
    ],
    'Mobile App - iOS': [
        'AppDelegate.swift', 'NetworkManager.swift',
        'DataSync.swift', 'UIController.swift',
        'PushHandler.swift', 'StorageManager.swift'
    ],
    'Mobile App - Android': [
        'MainActivity.kt', 'NetworkClient.kt',
        'DataRepository.kt', 'UIFragment.kt',
        'PushReceiver.kt', 'LocalDatabase.kt'
    ],
    'Integration Hub': [
        'IntegrationBroker.java', 'MessageTransformer.java',
        'ConnectorFactory.java', 'ErrorHandler.java',
        'RetryManager.java', 'SchemaValidator.java'
    ],
    'Admin Portal': [
        'AdminController.java', 'UserManager.java',
        'AuditLogger.java', 'ConfigService.java',
        'PermissionHandler.java', 'AdminDashboard.tsx'
    ],
    'Search Engine': [
        'SearchIndexer.java', 'QueryParser.java',
        'RankingEngine.java', 'CacheHandler.java',
        'FilterProcessor.java', 'SearchAPI.java'
    ],
    'Data Warehouse': [
        'ETLPipeline.java', 'DataTransformer.java',
        'LoadBalancer.java', 'SchemaMapper.java',
        'DataValidator.java', 'WarehouseConnector.java'
    ]
}

def get_rca(component):
    """Get weighted RCA for component"""
    options = RCA_CATEGORIES.get(component, [('Inadequate unit testing', 1.0)])
    rcas, weights = zip(*options)
    return np.random.choice(rcas, p=weights)

def get_code_segments(component, bug_count):
    """Get affected code segments based on bug count"""
    segments = CODE_SEGMENTS.get(component, ['UnknownFile.java'])
    num_affected = min(max(1, bug_count // 3), len(segments))
    return ', '.join(random.sample(segments, num_affected))

def generate_sprint_record(sprint_num, component):
    """Generate one sprint-level record"""
    risk = RISK_PROFILES[component]
    risk_multiplier = {'low': 0.6, 'medium': 1.0, 'high': 1.4, 'critical': 1.8}[risk]

    # Generate features
    story_points   = int(np.random.normal(55 * risk_multiplier, 12))
    story_points   = max(15, min(95, story_points))
    num_stories    = max(2, int(story_points / random.uniform(5, 10)))
    test_coverage  = max(20, min(95, np.random.normal(75 - (risk_multiplier * 10), 10)))
    code_churn     = max(200, int(np.random.normal(2000 * risk_multiplier, 500)))
    team_velocity  = max(20, int(np.random.normal(55, 12)))
    team_size      = max(3, int(np.random.normal(5 + risk_multiplier, 1.5)))
    complexity     = max(1, min(5, int(np.random.normal(2.5 * risk_multiplier, 1))))
    experience     = max(1.0, round(np.random.normal(4.0, 1.5), 1))
    dependencies   = max(1, int(np.random.normal(5 * risk_multiplier, 2)))
    prev_bugs      = max(0, int(np.random.normal(15 * risk_multiplier, 8)))

    # Bug count formula
    base_bugs = (
        (story_points * 0.12) +
        (prev_bugs * 0.15) +
        ((100 - test_coverage) * 0.08) +
        (code_churn * 0.001) +
        (complexity * 1.2) +
        (dependencies * 0.4) -
        (experience * 0.8) -
        (team_velocity * 0.05)
    ) * risk_multiplier

    bug_count = max(0, int(base_bugs + np.random.normal(0, 2)))
    rca = get_rca(component)
    code_segs = get_code_segments(component, bug_count)

    return {
        'sprint': f'Sprint-{sprint_num}',
        'sprint_number': sprint_num,
        'component': component,
        'component_risk_level': risk,
        'story_points': story_points,
        'num_stories': num_stories,
        'test_coverage': round(test_coverage, 1),
        'code_churn': code_churn,
        'team_velocity': team_velocity,
        'team_size': team_size,
        'complexity_score': complexity,
        'team_experience': experience,
        'dependencies': dependencies,
        'previous_bugs': prev_bugs,
        'bug_count': bug_count,
        'primary_rca': rca,
        'code_segments_impacted': code_segs
    }

# ══════════════════════════════════════════════════════════════
# GENERATE SPRINT DATA
# ══════════════════════════════════════════════════════════════
print("=" * 70)
print("GENERATING ENHANCED TRAINING DATA")
print("=" * 70)
print(f"\n📊 Generating {NUM_SPRINT_RECORDS} sprint records...")

sprint_records = []
sprint = 1
while len(sprint_records) < NUM_SPRINT_RECORDS:
    for component in COMPONENTS:
        if len(sprint_records) >= NUM_SPRINT_RECORDS:
            break
        sprint_records.append(generate_sprint_record(sprint, component))
    sprint += 1

sprint_df = pd.DataFrame(sprint_records)
sprint_df.to_csv('sprint_data_5000.csv', index=False)

print(f"✅ Generated {len(sprint_df)} sprint records")
print(f"   Sprints: {sprint_df['sprint_number'].nunique()}")
print(f"   Components: {sprint_df['component'].nunique()}")
print(f"\n📈 Bug count statistics:")
print(sprint_df['bug_count'].describe())
print(f"\n🔍 RCA distribution:")
print(sprint_df['primary_rca'].value_counts())
print(f"\n💾 Saved to: sprint_data_5000.csv")

print("\n" + "=" * 70)
print("✅ DATA GENERATION COMPLETE")
print("=" * 70)
