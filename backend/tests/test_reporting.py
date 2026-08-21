from app.reporting import build_executive_report

def test_structured_segmentation_report():
    result = {
        'route':'segmentation','analysis_type':'segmentation','target':None,'status':'COMPLETE','readiness':'FAST_EXECUTION_READY',
        'method':{'algorithm':'KMeans','clusters':2},
        'evidence':{'silhouette':0.3,'pca_variance':0.91},
        'findings':{'0':{'high':['A'],'low':['B'],'size_pct':60.0},'1':{'high':['B'],'low':['A'],'size_pct':40.0}},
        'warnings':[]
    }
    report = build_executive_report(result)
    assert report['overview'][0]['label'] == 'Analysis'
    assert report['findings'][0]['title'] == 'Segment 1'
    assert report['findings'][0]['subtitle'] == '60.0% of observations'
    assert 'Variance retained' in [x['label'] for x in report['evidence']]
    assert report['text']

def test_structured_association_report():
    result = {
        'route':'association','analysis_type':'association','target':None,'status':'COMPLETE','readiness':'FAST_EXECUTION_READY',
        'method':{'numeric_numeric':'Spearman'},
        'evidence':{'tests_run':10,'fdr_supported':4},
        'findings':[{'relationship':'A ↔ B','pair_type':'numeric_numeric','effect':0.8,'q_value':0.01,'interpretation':'positive association'}],
        'warnings':[]
    }
    report = build_executive_report(result)
    assert report['findings'][0]['title'] == 'A ↔ B'
    assert report['findings'][0]['effect'] == 0.8
    assert report['evidence'][0]['label'] == 'Tests run'
