"""Optional Matplotlib figures; all calculated graph data is exported separately."""
import math
from pathlib import Path
import textwrap


def check_available():
    try:
        import matplotlib
        matplotlib.use('Agg')
    except ImportError:
        raise ValueError('Figures require the analysis extra: python -m pip install -e ".[analysis]"') from None


def render_figures(folder, graphs, summary, *, max_nodes=40, scope_note="Captured report corpus"):
    check_available()
    import matplotlib.pyplot as plt
    with plt.rc_context({'text.parse_math': False, 'text.usetex': False}):
        return _render_figures(folder, graphs, summary, max_nodes=max_nodes, scope_note=scope_note)


def _render_figures(folder, graphs, summary, *, max_nodes=40, scope_note="Captured report corpus"):
    check_available()
    import matplotlib.pyplot as plt
    from matplotlib.ticker import MaxNLocator
    folder = Path(folder)
    views = []

    def save(fig, name, details):
        for suffix in ('svg', 'png'):
            fig.savefig(folder / f'{name}.{suffix}', dpi=160, facecolor='white')
        plt.close(fig)
        views.append({'figure': name, 'formats': ['svg', 'png'], **details})

    for kind, graph in graphs.items():
        ranked = sorted(graph['nodes'], key=lambda n: (-n['strength'], -n['occurrences'], n['id']))[:max_nodes]
        nodes = sorted(ranked, key=lambda n: n['id'])
        selected = {n['id'] for n in nodes}
        edges = [e for e in graph['edges'] if e['source'] in selected and e['target'] in selected]
        fig = plt.figure(figsize=(14, max(8, len(nodes) * 0.19 + 1.8)))
        ax = fig.add_axes([0.03, 0.16, 0.57, 0.73])
        ax.set_aspect('equal')
        ax.set_xlim(-1.25, 1.25)
        ax.set_ylim(-1.25, 1.25)
        ax.axis('off')
        positions = {node['id']: (math.cos(2 * math.pi * i / len(nodes)), math.sin(2 * math.pi * i / len(nodes))) for i, node in enumerate(nodes)}
        maximum = max((e['weight'] for e in edges), default=1)
        for edge in edges:
            a, b = positions[edge['source']], positions[edge['target']]
            ax.plot([a[0], b[0]], [a[1], b[1]], color='#64748b', linewidth=0.4 + 3 * edge['weight'] / maximum, alpha=0.55, zorder=1)
        for i, node in enumerate(nodes, 1):
            x, y = positions[node['id']]
            ax.scatter([x], [y], s=180, c=[plt.get_cmap('tab20')((node['cluster'] - 1) % 20)], edgecolors='#334155', zorder=2)
            ax.text(x, y, str(i), ha='center', va='center', fontsize=8, zorder=3)
        if not nodes:
            ax.text(0, 0, 'No nodes meet the thresholds.\nInspect metadata coverage and settings.', ha='center', va='center')
        legend = '\n'.join(f"{i}. {textwrap.shorten(n['label'], width=58, placeholder='…')} [C{n['cluster']}]" for i, n in enumerate(nodes, 1))
        fig.text(0.61, 0.87, legend, va='top', fontsize=8, family='sans-serif', linespacing=1.5)
        method = graph['methods']
        omitted = len(graph['nodes']) - len(nodes)
        fig.suptitle(kind.replace('_', ' ').title() + ' network', fontsize=16, y=0.96)
        caption = (f"{scope_note}. Full counting; normalization={method['normalization']}; min occurrences={method['min_occurrences']}; min raw edge count={method['min_edge_count']}.\n"
                   f"Circular display: distances have no analytical meaning. Shown {len(nodes)}/{len(graph['nodes'])} nodes and {len(edges)}/{len(graph['edges'])} edges; {omitted} nodes omitted.\n"
                   f"Colors: weighted label propagation on the full retained graph (20-color palette repeats). Edge width scales with chosen weight.\n"
                   f"Coverage: {graph['coverage']['records_with_usable_metadata']}/{graph['coverage']['records_total']} reports. Data/settings: {kind}.json and nodes/edges CSV.")
        fig.text(0.035, 0.035, caption, fontsize=8, va='bottom')
        save(fig, kind, {'data': f'{kind}.json', 'displayed_node_ids': [n['id'] for n in nodes],
                         'displayed_edges': len(edges), 'nodes_omitted': omitted, 'layout': 'sorted circular; no distance interpretation'})
    fig, ax = plt.subplots(figsize=(10, 6))
    rows = summary['publications_by_year']
    if rows:
        ax.bar([r['year'] for r in rows], [r['records'] for r in rows], color='#2563eb', width=0.8)
        ax.xaxis.set_major_locator(MaxNLocator(integer=True, nbins=12))
        ax.yaxis.set_major_locator(MaxNLocator(integer=True))
    else:
        ax.text(0.5, 0.5, 'No known publication years', ha='center', transform=ax.transAxes)
    ax.set(xlabel='Publication year', ylabel='Reports', title='Publication counts in the analyzed corpus')
    fig.subplots_adjust(bottom=0.19)
    fig.text(0.05, 0.03, f"{scope_note}. Full report counting; missing year: {summary['missing_years']}. Observed corpus only; no extrapolation.\nData: publications_by_year.csv; settings and provenance: methods.json / manifest.json.", fontsize=9)
    save(fig, 'publications_by_year', {'data': 'publications_by_year.csv', 'missing_years': summary['missing_years']})
    rows = summary['keyword_years']
    totals = {}
    for row in rows:
        totals[row['keyword']] = totals.get(row['keyword'], 0) + row['records']
    terms = sorted(totals, key=lambda k: (-totals[k], k))[:12]
    years = sorted({r['year'] for r in rows})
    fig, ax = plt.subplots(figsize=(12, 7))
    if terms and years:
        values = {(r['keyword'], r['year']): r['records'] for r in rows}
        matrix = [[values.get((term, year), 0) for year in years] for term in terms]
        image = ax.imshow(matrix, aspect='auto', cmap='Blues', vmin=0)
        tick_step = max(1, math.ceil(len(years) / 15))
        ticks = list(range(0, len(years), tick_step))
        ax.set_xticks(ticks, [str(years[i]) for i in ticks], rotation=45, ha='right')
        ax.set_yticks(range(len(terms)), [textwrap.shorten(t, width=40, placeholder='…') for t in terms])
        fig.colorbar(image, ax=ax, label='Reports with observed keyword', ticks=MaxNLocator(integer=True))
    else:
        ax.text(0.5, 0.5, 'No keywords with known publication years', ha='center', transform=ax.transAxes)
    ax.set_title('Observed keyword frequency by year')
    ax.set_xlabel('Observed publication years (equal column spacing)')
    fig.subplots_adjust(left=0.3, bottom=0.23, right=0.9, top=0.88)
    fig.text(0.04, 0.03, scope_note + '. Top 12 keywords by document frequency among reports with known years; binary incidence per report.\nZeros mean no observed keyword entries, not evidence of absence. This is not topic modeling or a research-gap inference.\nData: keyword_years.csv; settings and provenance: methods.json / manifest.json.', fontsize=9)
    save(fig, 'keyword_years', {'data': 'keyword_years.csv', 'displayed_keywords': terms, 'displayed_years': years,
                               'selection': 'top 12 by frequency among known-year reports, lexical ties'})
    return views
