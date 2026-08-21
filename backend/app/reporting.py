def build_executive_report(result):
    route = result.get('route')
    method = result.get('method', {})
    evidence = result.get('evidence', {})
    findings = result.get('findings', [])
    lines = [
        'ANALYSIS OVERVIEW',
        '-----------------',
        f'• Route: {route}',
        f"• Analysis type: {result.get('analysis_type')}",
        f"• Target: {result.get('target')}",
        f"• Status: {result.get('status')}",
        f"• Readiness: {result.get('readiness')}",
        '',
        'SELECTED METHOD',
        '---------------',
    ]

    for k, v in method.items():
        lines.append(f'• {k}: {v}')

    lines += ['', 'KEY EVIDENCE', '------------']
    for k, v in evidence.items():
        if isinstance(v, float):
            lines.append(f'• {k}: {v:.4f}')
        elif not isinstance(v, (dict, list)):
            lines.append(f'• {k}: {v}')

    if findings:
        lines += ['', 'KEY FINDINGS', '------------']
        if isinstance(findings, dict):
            for k, v in findings.items():
                lines.append(f'• {k}: {v}')
        else:
            for x in findings[:10]:
                lines.append(f'• {x}')

    warnings = result.get('warnings', [])
    if warnings:
        lines += ['', 'WARNINGS / GUARDRAILS', '---------------------']
        lines += [f'• {x}' for x in warnings]

    return {
        'route': route,
        'target': result.get('target'),
        'text': '\n'.join(lines),
    }
