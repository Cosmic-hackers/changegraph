import { useState } from 'react'
import { AlertTriangle, ArrowRight, BarChart3, CheckCircle2, ChevronDown, ChevronRight, CircleDot, Clock3, Code2, Database, FileCode2, GitBranch, History, Info, LoaderCircle, Play, RefreshCw, Search, ShieldCheck, Sparkles, TestTube2, XCircle, Zap } from 'lucide-react'
import { Background, Controls, Handle, MarkerType, MiniMap, Position, ReactFlow } from '@xyflow/react'
import '@xyflow/react/dist/style.css'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const emptyReport = {
  analysis: null,
  intelligence: null,
}

function App() {
  const [repository, setRepository] = useState('../sample_repos/test_shop')
  const [changeRequest, setChangeRequest] = useState('Change calculate_total to support discounts')
  const [report, setReport] = useState(emptyReport)
  const [status, setStatus] = useState('idle')
  const [error, setError] = useState('')

  async function runAnalysis(event) {
    event.preventDefault()
    setStatus('loading')
    setError('')
    setReport(emptyReport)
    try {
      const phase1Response = await fetch(`${API_URL}/api/analyze`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ repository, change_request: changeRequest }),
      })
      if (!phase1Response.ok) throw new Error(await readError(phase1Response, 'Deterministic analysis failed'))
      const analysis = await phase1Response.json()
      setReport({ analysis, intelligence: null })

      const intelligenceResponse = await fetch(`${API_URL}/api/analyze/intelligence`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ analysis }),
      })
      if (!intelligenceResponse.ok) throw new Error(await readError(intelligenceResponse, 'Intelligence analysis failed'))
      setReport({ analysis, intelligence: await intelligenceResponse.json() })
      setStatus('ready')
    } catch (requestError) {
      setError(requestError.message || 'Unable to reach the ChangeGraph API.')
      setStatus('error')
    }
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand"><span className="brand-mark"><GitBranch size={18} /></span><span>CHANGE<span>GRAPH</span></span></div>
        <div className="topbar-meta"><span className="status-dot" /> Local analysis workspace <span className="version">PHASE 3</span></div>
      </header>
      <main className="workspace">
        <aside className="control-rail">
          <div className="eyebrow">Impact workspace</div>
          <h1>Understand the blast radius.</h1>
          <p className="rail-copy">Turn a proposed code change into a grounded report before touching the implementation.</p>
          <form className="analysis-form" onSubmit={runAnalysis}>
            <label htmlFor="repository">Repository path</label>
            <div className="input-wrap"><Database size={16} /><input id="repository" value={repository} onChange={(event) => setRepository(event.target.value)} placeholder="./repository" /></div>
            <label htmlFor="change-request">Change request</label>
            <textarea id="change-request" value={changeRequest} onChange={(event) => setChangeRequest(event.target.value)} rows="4" placeholder="Describe the change you are considering..." />
            <button className="primary-button" type="submit" disabled={status === 'loading' || !repository || !changeRequest}>
              {status === 'loading' ? <LoaderCircle className="spin" size={17} /> : <Play size={17} />}
              {status === 'loading' ? 'Analyzing repository' : 'Generate impact report'}
            </button>
          </form>
          <div className="rail-note"><Info size={15} /><span>Relationships and evidence come from the deterministic repository analyzer. AI reasoning is shown separately.</span></div>
        </aside>
        <section className="report-area">
          {status === 'idle' && <EmptyState onDemo={runAnalysis} />}
          {status === 'loading' && <LoadingState />}
          {status === 'error' && <ErrorState message={error} onRetry={runAnalysis} />}
          {report.analysis && <Report analysis={report.analysis} intelligence={report.intelligence} />}
        </section>
      </main>
    </div>
  )
}

async function readError(response, fallback) {
  try { const body = await response.json(); return body.detail || fallback } catch { return fallback }
}

function EmptyState({ onDemo }) {
  return <div className="empty-state"><div className="empty-icon"><GitBranch size={28} /></div><div className="eyebrow">Ready when you are</div><h2>Your next change, mapped.</h2><p>Enter a repository and proposed change to generate a developer-focused impact report with dependency evidence, risk signals, and test guidance.</p><button className="secondary-button" onClick={onDemo}><Zap size={16} /> Analyze sample repository</button></div>
}

function LoadingState() {
  return <div className="loading-state"><LoaderCircle className="spin loading-icon" size={34} /><h2>Tracing repository relationships</h2><p>Parsing symbols, walking dependencies, and preparing grounded reasoning.</p><div className="loading-lines"><span /><span /><span /></div></div>
}

function ErrorState({ message, onRetry }) {
  return <div className="error-state"><XCircle size={34} /><div><div className="eyebrow">Analysis unavailable</div><h2>We could not generate this report.</h2><p>{message}</p><button className="secondary-button" onClick={onRetry}><RefreshCw size={16} /> Try again</button></div></div>
}

function Report({ analysis, intelligence }) {
  const [activeTab, setActiveTab] = useState('overview')
  return <div className="report">
    <div className="report-heading"><div><div className="eyebrow">Change impact report</div><h2>{analysis.change_request}</h2><div className="report-path"><Database size={14} /> {analysis.repository_path}</div></div><div className="heading-actions"><span className="deterministic-badge"><ShieldCheck size={14} /> Deterministic + AI grounded</span></div></div>
    <nav className="report-tabs" aria-label="Report views"><button className={activeTab === 'overview' ? 'active' : ''} onClick={() => setActiveTab('overview')}><BarChart3 size={15} /> Overview</button><button className={activeTab === 'graph' ? 'active' : ''} onClick={() => setActiveTab('graph')}><GitBranch size={15} /> Dependency graph</button><button className={activeTab === 'evidence' ? 'active' : ''} onClick={() => setActiveTab('evidence')}><ShieldCheck size={15} /> Evidence & reasoning</button></nav>
    {activeTab === 'overview' && <Overview analysis={analysis} intelligence={intelligence} />}
    {activeTab === 'graph' && <GraphSection analysis={analysis} />}
    {activeTab === 'evidence' && <EvidenceSection analysis={analysis} intelligence={intelligence} />}
  </div>
}

function Overview({ analysis, intelligence }) {
  const risk = intelligence?.risk_analysis?.assessed_risk_level || analysis.risk_level
  return <>
    <section className="summary-grid"><article className="summary-card summary-card-wide"><div className="card-label"><Sparkles size={15} /> Change summary <span className="source-tag ai">AI synthesis</span></div><p className="summary-text">{intelligence?.executive_summary || 'Deterministic analysis is complete. AI synthesis is still being prepared.'}</p></article><article className={`summary-card risk-card risk-${risk.toLowerCase()}`}><div className="card-label"><ShieldCheck size={15} /> Risk level</div><strong>{risk}</strong><span>{intelligence?.risk_analysis?.risk_justification?.[0] || analysis.risk_reasons?.[0] || 'Awaiting risk assessment'}</span></article></section>
    <div className="metric-strip"><Metric label="Changed files" value={analysis.affected_files.length} icon={<FileCode2 />} /><Metric label="Direct impact" value={analysis.direct_impact.length} icon={<ArrowRight />} /><Metric label="Indirect impact" value={analysis.indirect_impact.length} icon={<CircleDot />} /><Metric label="Graph nodes" value={analysis.graph_summary?.nodes || 0} icon={<GitBranch />} /></div>
    <Section title="Changed files" icon={<FileCode2 />} source="deterministic"><FileList files={analysis.affected_files} changed={analysis.changed_components} /></Section>
    <div className="two-column"><Section title="Direct impact" icon={<ArrowRight />} source="deterministic"><ImpactList items={analysis.direct_impact} /></Section><Section title="Indirect impact" icon={<CircleDot />} source="deterministic"><ImpactList items={analysis.indirect_impact} /></Section></div>
    <Section title="Recommended tests" icon={<TestTube2 />} source="deterministic + AI"><TestStrategy analysis={analysis} intelligence={intelligence} /></Section>
    <Section title="Git history context" icon={<History />} source="deterministic + AI"><HistoryContext analysis={analysis} intelligence={intelligence} /></Section>
  </>
}

function Metric({ label, value, icon }) { return <div className="metric"><span className="metric-icon">{icon}</span><span><strong>{value}</strong><small>{label}</small></span></div> }
function Section({ title, icon, source, children }) { return <section className="report-section"><div className="section-heading"><h3>{icon}{title}</h3><span className={`source-tag ${source.includes('AI') ? 'mixed' : 'deterministic'}`}>{source}</span></div>{children}</section> }

function FileRow({ file, target }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="file-row-wrap">
      <button className="file-row" onClick={() => target && setOpen(!open)} style={target ? {cursor:'pointer'} : {cursor:'default'}}>
        <FileCode2 size={16} />
        <span className="file-name">{file}</span>
        {target && <span className="function-pill">{target.symbol}</span>}
        {target ? (open ? <ChevronDown size={15} /> : <ChevronRight size={15} />) : <ChevronRight size={15} style={{opacity:0.2}} />}
      </button>
      {open && target && (
        <div className="file-row-detail">
          <div className="file-row-detail-row"><Code2 size={13} /><span className="file-row-module">{target.module}</span><span className="muted">/ {target.file_path}</span></div>
          {target.reason && <p className="file-row-reason">{target.reason}</p>}
        </div>
      )}
    </div>
  )
}

function FileList({ files, changed }) {
  return <div className="file-list">{files.length ? files.map((file) => {
    const target = changed.find((c) => c.file_path === file)
    return <FileRow key={file} file={file} target={target} />
  }) : <EmptyInline text="No affected files were detected." />}</div>
}

function ImpactList({ items }) { return items.length ? <div className="impact-list">{items.map((item) => <ImpactItem item={item} key={item.key} />)}</div> : <EmptyInline text="No impacted components in this category." /> }
function ImpactItem({ item }) { const [open, setOpen] = useState(false); return <div className="impact-item"><button className="impact-toggle" onClick={() => setOpen(!open)}>{open ? <ChevronDown size={16} /> : <ChevronRight size={16} />}<span className="impact-name">{item.name}</span><span className="node-type">{item.node_type}</span><span className="depth">D{item.depth}</span></button>{open && <div className="impact-detail"><div><Code2 size={14} /> {item.module} <span className="muted">/ {item.file_path}</span></div><p>{item.explanation}</p>{item.path?.length > 0 && <div className="path-line">{item.path.join('  →  ')}</div>}</div>}</div> }
function EmptyInline({ text }) { return <div className="empty-inline"><Info size={15} />{text}</div> }

function TestStrategy({ analysis, intelligence }) { const suites = intelligence?.test_strategy?.recommended_suites || []; return <div className="test-layout"><div className="test-list">{suites.length ? suites.map((suite) => <div className="test-row" key={suite.test_file}><span className={`priority priority-${suite.priority.toLowerCase()}`}>{suite.priority}</span><div><strong>{suite.test_module}</strong><span>{suite.test_file}</span><p>{suite.rationale}</p></div><TestTube2 size={17} /></div>) : analysis.recommended_tests.map((test) => <div className="test-row" key={test.file_path}><span className="priority priority-medium">RUN</span><div><strong>{test.module_name}</strong><span>{test.file_path}</span><p>{test.match_reasons.join(' · ')}</p></div><TestTube2 size={17} /></div>)}</div>{intelligence?.test_strategy?.coverage_gaps?.length > 0 && <div className="coverage-gaps"><div className="mini-label">Coverage gaps</div>{intelligence.test_strategy.coverage_gaps.map((gap) => <div className="gap" key={gap.component}><AlertTriangle size={14} /><span><strong>{gap.component}</strong>{gap.suggested_test_scenario}</span></div>)}</div>}</div> }

function HistoryContext({ analysis, intelligence }) { const git = analysis.git_context; return <div className="history-layout"><div className="history-summary"><div className="history-state">{git?.git_available ? <CheckCircle2 size={17} /> : <Info size={17} />}<strong>{git?.git_available ? 'Git history available' : 'No Git history available'}</strong></div><p>{intelligence?.history_context?.historical_summary || (git?.error || 'History context was not returned for this repository.')}</p>{intelligence?.history_context?.historical_risk_notes?.map((note) => <div className="note" key={note}><AlertTriangle size={14} />{note}</div>)}</div><div className="churn-list">{Object.values(git?.file_histories || {}).slice(0, 4).map((file) => <div className="churn-row" key={file.file_path}><span>{file.relative_path}</span><span className="churn-score">{file.churn_score} churn</span></div>)}</div></div> }

function GraphSection({ analysis }) { return <Section title="Dependency graph" icon={<GitBranch />} source="deterministic"><div className="graph-intro"><p>Deterministic dependency paths from changed components through direct and indirect dependents.</p><span><span className="legend-dot changed" /> changed <span className="legend-dot direct" /> direct <span className="legend-dot indirect" /> indirect</span></div><DependencyGraph analysis={analysis} /></Section> }

function DependencyGraph({ analysis }) { const graph = buildGraph(analysis); return <div className="graph-canvas"><ReactFlow nodes={graph.nodes} edges={graph.edges} nodeTypes={{ impact: ImpactNode }} fitView fitViewOptions={{ padding: 0.25 }} minZoom={0.25} maxZoom={1.5}><Background color="#273039" gap={24} /><Controls showInteractive={false} /><MiniMap nodeColor={(node) => node.data.tone === 'changed' ? '#d6f36b' : node.data.tone === 'direct' ? '#62d5c8' : '#53616c'} maskColor="rgba(10, 14, 18, .75)" /></ReactFlow></div> }
function ImpactNode({ data }) { const [expanded, setExpanded] = useState(false); return <div className={`graph-node tone-${data.tone} ${expanded ? 'expanded' : ''}`} onClick={() => setExpanded(!expanded)}><Handle type="target" position={Position.Left} /> <div className="node-top"><span className="node-symbol">{data.label}</span><span className="node-kind">{data.kind}</span></div>{expanded && <div className="node-file">{data.file}</div>}<Handle type="source" position={Position.Right} /></div> }
function buildGraph(analysis) { const all = [...analysis.changed_components.map((item) => ({ ...item, tone: 'changed', kind: 'changed' })), ...analysis.direct_impact.map((item) => ({ ...item, symbol: item.name, tone: 'direct', kind: 'direct' })), ...analysis.indirect_impact.map((item) => ({ ...item, symbol: item.name, tone: 'indirect', kind: 'indirect' }))]; const byKey = new Map(all.map((item) => [item.key, item])); const byLabel = new Map(all.map((item) => [item.key.split(':').pop(), item])); const nodes = all.map((item, index) => ({ id: item.key, type: 'impact', position: { x: (item.depth || 0) * 260, y: (index % 8) * 82 }, data: { label: item.symbol, kind: item.kind, tone: item.tone, file: item.file_path } })); const edges = []; analysis.dependency_paths.forEach((path) => path.slice(0, -1).forEach((from, index) => { const source = byKey.has(from) ? from : byLabel.get(from)?.key; const targetValue = path[index + 1]; const target = byKey.has(targetValue) ? targetValue : byLabel.get(targetValue)?.key; if (source && target && !edges.some((edge) => edge.source === source && edge.target === target)) edges.push({ id: `${source}-${target}`, source, target, markerEnd: { type: MarkerType.ArrowClosed, color: '#657680' }, style: { stroke: '#657680' } }) })); return { nodes, edges } }

function EvidenceSection({ analysis, intelligence }) { return <><Section title="AI reasoning" icon={<Sparkles />} source="AI grounded"><div className="reasoning-layout"><div className="reasoning-main"><p className="reasoning-summary">{intelligence?.impact_reasoning?.summary || 'AI reasoning is still being prepared.'}</p>{intelligence?.impact_reasoning?.affected_workflows?.map((workflow) => <div className="workflow" key={workflow.workflow_name}><div><strong>{workflow.workflow_name}</strong><span className={`criticality criticality-${workflow.criticality.toLowerCase()}`}>{workflow.criticality}</span></div><p>{workflow.impact_explanation}</p><div className="path-line">{workflow.propagation_chain}</div></div>)}</div><div className="reasoning-side"><div className="mini-label">Failure scenarios</div>{intelligence?.risk_analysis?.failure_scenarios?.map((scenario) => <div className="scenario" key={scenario.component}><AlertTriangle size={15} /><div><strong>{scenario.component}</strong><p>{scenario.scenario_description}</p><small>{scenario.mitigation_advice}</small></div></div>)}</div></div></Section><Section title="Evidence audit" icon={<ShieldCheck />} source="deterministic"><EvidenceAudit analysis={analysis} intelligence={intelligence} /></Section></> }
function EvidenceAudit({ intelligence }) { const evidence = intelligence?.evidence; if (!evidence) return <EmptyInline text="Intelligence evidence is still being prepared." />; return <div className="audit-grid"><Audit label="Nodes evaluated" value={evidence.deterministic_nodes_evaluated} /><Audit label="Edges evaluated" value={evidence.deterministic_edges_evaluated} /><Audit label="Direct dependents" value={evidence.direct_dependents_count} /><Audit label="Validated symbols" value={evidence.validated_symbol_count} /><div className="audit-provider"><span>Provider</span><strong>{evidence.ai_provider_used}</strong><small>{evidence.generation_mode.replace('_', ' ')}</small></div>{evidence.unverified_claims_filtered?.length > 0 && <div className="filtered-claims"><div className="mini-label">Filtered claims</div>{evidence.unverified_claims_filtered.map((claim) => <div key={claim}><ShieldCheck size={14} />{claim}</div>)}</div>}</div> }
function Audit({ label, value }) { return <div className="audit-item"><strong>{value}</strong><span>{label}</span></div> }

export default App