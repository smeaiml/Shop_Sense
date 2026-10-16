import { useState, type FormEvent, type ReactNode } from 'react';
import { QueryClient, QueryClientProvider, useQueryClient } from '@tanstack/react-query';
import {
  useGetShopSenseDashboard,
  useListSupportTickets,
  useListPendingReviews,
  useSubmitSupportMessage,
  useResumeSupportReview,
  useLookupCustomerOrder,
  useAskShopSensePolicy,
  useGetCustomerMemory,
  useUpdateCustomerMemory,
  getGetShopSenseDashboardQueryKey,
  getListSupportTicketsQueryKey,
  getListPendingReviewsQueryKey,
  getGetCustomerMemoryQueryKey,
} from '@workspace/api-client-react';
import {
  Activity, ArrowRight, BadgeCheck, BookOpen, Check,
  CheckCircle2, CircleHelp, Clock3, CreditCard, FileText, Headphones,
  Inbox, Menu, MessageSquareText, PackageCheck, Search, Send, ShieldCheck,
  ShoppingBag, Sparkles, Users, X, AlertCircle, RotateCcw, UserRound, Truck,
} from 'lucide-react';
import { Link, Route, Router, Switch, useLocation } from 'wouter';
import NotFound from '@/pages/not-found';

const queryClient = new QueryClient();

type Notify = (message: string) => void;
const nice = (value?: string | null) => (value || '—').replaceAll('_', ' ');
const shortDate = (value?: string | null) => {
  if (!value) return '—';
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
};
const refText = (value: unknown) => value === null || value === undefined ? '—' : String(value);
const getValue = (record: unknown, keys: string[]) => {
  if (!record || typeof record !== 'object') return undefined;
  for (const key of keys) {
    const value = (record as Record<string, unknown>)[key];
    if (value !== null && value !== undefined && value !== '') return value;
  }
  return undefined;
};
const initials = (value: string) => value.split(/[\s_-]/).filter(Boolean).slice(0, 2).map((part) => part[0]?.toUpperCase()).join('') || 'C';

function Badge({ value }: { value: string }) {
  const normalized = value.toLowerCase().replaceAll(' ', '_');
  const mood = ['open', 'pending', 'resolved', 'approved', 'escalated', 'high', 'urgent', 'in_progress'].includes(normalized) ? normalized : 'neutral';
  return <span className={`badge ${mood}`} data-testid={`status-${normalized}`}>{nice(value)}</span>;
}

function PageHeading({ eyebrow, title, intro, action }: { eyebrow: string; title: string; intro: string; action?: ReactNode }) {
  return <div className="page-heading"><div><div className="eyebrow">{eyebrow}</div><h1 className="page-title">{title}</h1><p className="page-intro">{intro}</p></div>{action}</div>;
}

function LoadingCards({ count = 3 }: { count?: number }) {
  return <div className="metrics">{Array.from({ length: count }, (_, index) => <div className="skeleton-card" key={index}><div className="skeleton" style={{ width: '44%' }} /><div className="skeleton" style={{ width: '65%', height: 27 }} /></div>)}</div>;
}

function ErrorState({ message, retry }: { message: string; retry: () => void }) {
  return <div className="error-state" role="alert"><AlertCircle size={19} /><span>{message}</span><button className="button secondary small" onClick={retry} data-testid="button-retry"><RotateCcw size={13} /> Try again</button></div>;
}

function EmptyState({ icon, title, copy }: { icon: ReactNode; title: string; copy: string }) {
  return <div className="empty-state"><div className="empty-mark">{icon}</div><div className="empty-title">{title}</div><p className="empty-copy">{copy}</p></div>;
}

function TicketRow({ ticket }: { ticket: import('@workspace/api-client-react').SupportTicketSummary }) {
  return <div className="ticket-row" data-testid={`row-ticket-${ticket.ticket_id}`}>
    <div className="ticket-main"><div className="ticket-title"><span>{nice(ticket.issue_type)}</span><span className="ticket-id">{ticket.ticket_id}</span></div>
      <div className="ticket-meta"><span>Customer {ticket.customer_id || 'unlinked'}</span>{ticket.order_id && <span>Order {ticket.order_id}</span>}<span>{nice(ticket.sentiment)} sentiment</span></div></div>
    <div className="ticket-side"><Badge value={ticket.status} /><span className="time">{shortDate(ticket.created_at)}</span></div>
  </div>;
}

function AppShell({ children, notify }: { children: ReactNode; notify: Notify }) {
  const [location] = useLocation();
  const [mobileNav, setMobileNav] = useState(false);
  const [toast, setToast] = useState('');
  const announce = (message: string) => {
    setToast(message);
    window.setTimeout(() => setToast(''), 3200);
    notify(message);
  };
  const navItems = [
    { href: '/', label: 'Overview', icon: Activity },
    { href: '/tickets', label: 'Tickets', icon: Inbox },
    { href: '/reviews', label: 'Reviews', icon: ShieldCheck },
    { href: '/orders', label: 'Order lookup', icon: ShoppingBag },
    { href: '/policies', label: 'Policy desk', icon: BookOpen },
  ];
  const activeLabel = navItems.find((item) => item.href === location)?.label || (location.startsWith('/customers/') ? 'Customer profile' : 'Support desk');
  return <div className="app-shell">
    {mobileNav && <div className="mobile-backdrop" onClick={() => setMobileNav(false)} />}
    <aside className={`sidebar ${mobileNav ? 'open' : ''}`}>
      <div className="brand"><div className="brand-mark"><Headphones size={20} strokeWidth={2.2} /></div><div><div className="brand-name">shopsense</div><div className="brand-sub">care operations</div></div></div>
      <div className="nav-group"><div className="nav-label">Workspace</div>{navItems.map(({ href, label, icon: Icon }) => <Link key={href} href={href} className={`nav-link ${location === href ? 'active' : ''}`} onClick={() => setMobileNav(false)} data-testid={`link-${label.toLowerCase().replaceAll(' ', '-')}`}><Icon size={16} /><span>{label}</span></Link>)}</div>
      <div className="nav-group"><div className="nav-label">Customer care</div><Link href="/customers/lookup" className={`nav-link ${location.startsWith('/customers/') ? 'active' : ''}`} onClick={() => setMobileNav(false)}><Users size={16} /><span>Customer memory</span></Link></div>
      <div className="side-bottom"><div className="agent"><div className="avatar">AM</div><div><div className="agent-name">Avery Morgan</div><div className="agent-role">Support specialist</div></div></div></div>
    </aside>
    <main className="main-area">
      <header className="topbar"><div style={{ display: 'flex', alignItems: 'center', gap: 12 }}><button className="icon-button mobile-menu" aria-label="Open navigation" onClick={() => setMobileNav(true)} data-testid="button-open-navigation"><Menu size={17} /></button><span className="crumb">Support / {activeLabel}</span></div>
        <div className="top-actions"><div className="top-status"><span className="live-dot" /> All systems steady</div><button className="icon-button" title="Help center" onClick={() => announce('Help resources are available in the policy desk.')} data-testid="button-help"><CircleHelp size={16} /></button><div className="avatar" style={{ width: 31, height: 31, fontSize: 10 }}>AM</div></div></header>
      {children}
    </main>
    {toast && <div className="toast-region"><div className="toast-message" role="status">{toast}</div></div>}
  </div>;
}

function Dashboard() {
  const query = useGetShopSenseDashboard();
  const data = query.data;
  return <div className="page">
    <PageHeading eyebrow="Monday, your queue is ready" title="Good morning, Avery." intro="A clear view of what needs care today." action={<Link href="/tickets" className="button"><MessageSquareText size={15} /> Open ticket desk</Link>} />
    {query.isLoading ? <LoadingCards /> : query.isError ? <ErrorState message="We couldn't load the support overview." retry={() => query.refetch()} /> : data && <>
      <div className="metrics">
        <Metric icon={<Inbox size={16} />} label="Open tickets" value={data.open_tickets} note="In your queue" />
        <Metric icon={<ShieldCheck size={16} />} label="Awaiting review" value={data.pending_reviews} note="Needs a second look" />
        <Metric icon={<CheckCircle2 size={16} />} label="Resolved today" value={data.resolved_today} note="Good work, team" />
        <Metric icon={<Users size={16} />} label="Customers helped" value={data.customers_served} note="Today so far" />
      </div>
      <div className="dashboard-grid">
        <section className="panel"><div className="panel-head"><div><h2 className="panel-title">Recent conversations</h2><div className="panel-sub">The latest activity across your support desk</div></div><Link href="/tickets" className="text-link">All tickets <ArrowRight size={13} /></Link></div>
          <div className="panel-body"><div className="ticket-list">{data.recent_tickets?.length ? data.recent_tickets.map((ticket) => <TicketRow key={ticket.ticket_id} ticket={ticket} />) : <EmptyState icon={<Inbox size={20} />} title="A little breathing room" copy="New customer conversations will appear here as they arrive." />}</div></div></section>
        <section className="panel"><div className="panel-head"><div><h2 className="panel-title">Review desk</h2><div className="panel-sub">Requests that need your judgment</div></div><ShieldCheck size={17} color="#5e9572" /></div>
          <div className="panel-body"><div className="queue-card"><div className="queue-icon"><Clock3 size={19} /></div><div><div className="queue-number">{data.pending_reviews}</div><div className="queue-label">waiting for approval</div></div></div><Link href="/reviews" className="button" style={{ width: '100%' }}>Go to reviews <ArrowRight size={14} /></Link><p className="queue-note">A second pair of eyes keeps every customer promise fair, clear, and within policy.</p></div></section>
      </div>
    </>}
  </div>;
}

function Metric({ icon, label, value, note }: { icon: ReactNode; label: string; value: number; note: string }) {
  return <div className="metric"><div className="metric-label">{icon}{label}</div><div className="metric-number">{value}<span className="metric-note">{note}</span></div></div>;
}

function Tickets() {
  const [filter, setFilter] = useState('');
  const [search, setSearch] = useState('');
  const [message, setMessage] = useState('');
  const [customer, setCustomer] = useState('');
  const [order, setOrder] = useState('');
  const [result, setResult] = useState<import('@workspace/api-client-react').SupportWorkflowResult | null>(null);
  const query = useListSupportTickets(filter ? { status: filter } : undefined);
  const mutation = useSubmitSupportMessage();
  const client = useQueryClient();
  const filtered = (query.data || []).filter((ticket) => [ticket.ticket_id, ticket.customer_id, ticket.order_id, ticket.issue_type].some((value) => value?.toLowerCase().includes(search.toLowerCase())));
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!message.trim()) return;
    mutation.mutate({ data: { message: message.trim(), customer_id: customer.trim() || undefined, order_id: order.trim() || undefined } }, {
      onSuccess: (response) => {
        setResult(response); setMessage('');
        client.invalidateQueries({ queryKey: getListSupportTicketsQueryKey() });
        client.invalidateQueries({ queryKey: getGetShopSenseDashboardQueryKey() });
        client.invalidateQueries({ queryKey: getListPendingReviewsQueryKey() });
      },
    });
  };
  return <div className="page">
    <PageHeading eyebrow="Customer conversations" title="Ticket desk" intro="Triage the latest requests, then start or continue a conversation." />
    <div className="tabs"><span className="tab active">All tickets & intake</span></div>
    <div className="ticket-layout">
      <section className="panel"><div className="panel-head"><div><h2 className="panel-title">Ticket queue</h2><div className="panel-sub">{query.data?.length ?? '—'} conversations in view</div></div><Badge value={filter || 'all tickets'} /></div>
        <div className="toolbar"><div className="search-wrap"><Search size={15} /><input className="field" placeholder="Search ticket, customer, order…" value={search} onChange={(event) => setSearch(event.target.value)} aria-label="Search tickets" data-testid="input-search-tickets" /></div><select className="select" aria-label="Filter tickets by status" value={filter} onChange={(event) => setFilter(event.target.value)} data-testid="select-ticket-status"><option value="">Every status</option><option value="open">Open</option><option value="pending">Pending</option><option value="resolved">Resolved</option><option value="escalated">Escalated</option></select></div>
        {query.isLoading ? <div className="panel-body"><div className="skeleton" style={{ height: 120 }} /></div> : query.isError ? <div className="panel-body"><ErrorState message="Ticket list unavailable right now." retry={() => query.refetch()} /></div> : filtered.length ? <div className="panel-body"><div className="ticket-list">{filtered.map((ticket) => <TicketRow ticket={ticket} key={ticket.ticket_id} />)}</div></div> : <EmptyState icon={<Inbox size={20} />} title={search || filter ? 'No matching tickets' : 'No tickets in this queue'} copy={search || filter ? 'Try another search or status filter.' : 'New customer conversations will appear here.'} />}
      </section>
      <section className="panel"><div className="panel-head"><div><h2 className="panel-title">New conversation</h2><div className="panel-sub">Share the customer’s request for a grounded response</div></div><Sparkles size={16} color="#589174" /></div>
        {result && <div className="conversation" style={{ minHeight: 0, paddingBottom: 4 }}><div className="message customer"><div className="message-label">Workflow status · {nice(result.status)}</div>{result.decision_message || result.human_review_reason || 'Request received and routed for the next step.'}</div>{result.response && <div className="message agent"><div className="message-label">Suggested response</div>{result.response}</div>}
          {result.approval_required && <div className="error-state"><ShieldCheck size={17} /><span>Approval required{result.approval_tier ? ` · ${result.approval_tier}` : ''}. This request is now in the review desk.</span></div>}</div>}
        <form className="compose" onSubmit={submit}><div className="form-row"><div className="field-group"><label className="field-label" htmlFor="ticket-customer">Customer reference <span style={{ fontWeight: 400 }}>(optional)</span></label><input id="ticket-customer" className="field" value={customer} onChange={(event) => setCustomer(event.target.value)} placeholder="Customer ID" data-testid="input-ticket-customer" /></div><div className="field-group"><label className="field-label" htmlFor="ticket-order">Order reference <span style={{ fontWeight: 400 }}>(optional)</span></label><input id="ticket-order" className="field" value={order} onChange={(event) => setOrder(event.target.value)} placeholder="Order ID" data-testid="input-ticket-order" /></div></div>
          <label className="field-label" htmlFor="ticket-message">Customer message</label><textarea id="ticket-message" className="textarea" maxLength={5000} value={message} onChange={(event) => setMessage(event.target.value)} placeholder="What can we help them with?" data-testid="input-ticket-message" />
          {mutation.isError && <div style={{ color: '#a65342', fontSize: 11, marginTop: 9 }} role="alert">Couldn’t submit this message. Check the details and try again.</div>}
          <div className="compose-foot"><span className="hint">ShopSense will check policy and route approvals.</span><button className="button" disabled={mutation.isPending || !message.trim()} data-testid="button-submit-ticket"><Send size={14} />{mutation.isPending ? 'Working…' : 'Process message'}</button></div>
        </form>
      </section>
    </div>
  </div>;
}

function Reviews() {
  const query = useListPendingReviews();
  const mutation = useResumeSupportReview();
  const client = useQueryClient();
  const [pendingId, setPendingId] = useState('');
  const decide = (ticket: import('@workspace/api-client-react').SupportTicketSummary, approved: boolean) => {
    setPendingId(ticket.ticket_id);
    const role = (ticket.approval_tier || '').toLowerCase();
    const approver_role = (['agent', 'team_lead', 'ops_manager', 'finance'] as const).find((allowedRole) => allowedRole === role);
    mutation.mutate({ data: { thread_id: ticket.ticket_id, reviewer_id: 'Avery Morgan', approved, ...(approved && approver_role ? { approver_role } : {}) } }, {
      onSuccess: () => {
        client.invalidateQueries({ queryKey: getListPendingReviewsQueryKey() });
        client.invalidateQueries({ queryKey: getListSupportTicketsQueryKey() });
        client.invalidateQueries({ queryKey: getGetShopSenseDashboardQueryKey() });
        setPendingId('');
      },
      onError: () => setPendingId(''),
    });
  };
  return <div className="page"><PageHeading eyebrow="Human review queue" title="A thoughtful second look." intro="Review requests that need an agent’s judgment before the next customer step." />
    <div className="metrics" style={{ gridTemplateColumns: 'minmax(0,260px)' }}><Metric icon={<Clock3 size={16} />} label="Waiting for review" value={query.data?.length || 0} note="In queue" /></div>
    {mutation.isError && <div style={{ marginBottom: 14 }}><ErrorState message="That review decision could not be saved. Please try again." retry={() => mutation.reset()} /></div>}
    {query.isLoading ? <div className="review-list"><div className="skeleton-card" /><div className="skeleton-card" /></div> : query.isError ? <ErrorState message="Review queue unavailable right now." retry={() => query.refetch()} /> : query.data?.length ? <div className="review-list">{query.data.map((ticket) => <article className="review-card" key={ticket.ticket_id} data-testid={`card-review-${ticket.ticket_id}`}><div><div style={{ display: 'flex', alignItems: 'center', gap: 9, flexWrap: 'wrap' }}><span className="ticket-id">{ticket.ticket_id}</span><Badge value={ticket.urgency} /><Badge value={ticket.approval_tier || 'human review'} /></div><h2 className="panel-title" style={{ marginTop: 10 }}>{nice(ticket.issue_type)} · customer {ticket.customer_id || 'not linked'}</h2><p className="review-reason">{ticket.response || 'A human review is requested before we respond to this customer.'}</p><div className="ticket-meta"><span>Received {shortDate(ticket.created_at)}</span>{ticket.order_id && <span>Order {ticket.order_id}</span>}</div></div><div className="review-actions"><button className="button secondary small" disabled={pendingId === ticket.ticket_id} onClick={() => decide(ticket, false)} data-testid={`button-reject-${ticket.ticket_id}`}><X size={13} /> Reject</button><button className="button small" disabled={pendingId === ticket.ticket_id} onClick={() => decide(ticket, true)} data-testid={`button-approve-${ticket.ticket_id}`}><Check size={13} />{pendingId === ticket.ticket_id ? 'Saving…' : 'Approve'}</button></div></article>)}</div> : <section className="panel"><EmptyState icon={<BadgeCheck size={20} />} title="Nothing waiting on you" copy="When a support workflow needs approval, it will be held here for a careful review." /></section>}
  </div>;
}

function Orders() {
  const mutation = useLookupCustomerOrder();
  const [orderRef, setOrderRef] = useState('');
  const [customerRef, setCustomerRef] = useState('');
  const submit = (event: FormEvent) => { event.preventDefault(); if (orderRef.trim() && customerRef.trim()) mutation.mutate({ data: { order_ref: orderRef.trim(), customer_ref: customerRef.trim() } }); };
  const result = mutation.data;
  const orderNumber = getValue(result?.order, ['order_id', 'order_ref', 'id', 'number']);
  const shipmentStatus = getValue(result?.shipment, ['status', 'shipment_status', 'state']);
  return <div className="page"><PageHeading eyebrow="Customer-scoped order lookup" title="Find the full order story." intro="Order details are shown only when the customer reference matches the order owner." />
    <div className="lookup-grid"><section className="panel"><div className="panel-head"><div><h2 className="panel-title">Look up an order</h2><div className="panel-sub">Enter both references to check ownership and fulfillment</div></div><PackageCheck size={18} color="#5e9572" /></div><div className="panel-body">
      <form onSubmit={submit}><div className="form-row"><div className="field-group"><label className="field-label" htmlFor="order-ref">Order reference</label><input className="field" id="order-ref" value={orderRef} onChange={(event) => setOrderRef(event.target.value)} placeholder="e.g. ORD-2481" required data-testid="input-order-reference" /></div><div className="field-group"><label className="field-label" htmlFor="customer-ref">Customer reference</label><input className="field" id="customer-ref" value={customerRef} onChange={(event) => setCustomerRef(event.target.value)} placeholder="Customer ID" required data-testid="input-order-customer" /></div></div><button className="button" disabled={mutation.isPending} data-testid="button-lookup-order"><Search size={14} />{mutation.isPending ? 'Checking ownership…' : 'Look up order'}</button></form>
      {mutation.isError && <div style={{ marginTop: 15 }}><ErrorState message="We couldn't retrieve this order. Check both references and retry." retry={() => mutation.mutate({ data: { order_ref: orderRef.trim(), customer_ref: customerRef.trim() } })} /></div>}
      {result && <div style={{ marginTop: 22 }} data-testid="order-lookup-result">{result.found ? <>
        <div className="result-hero"><div><div className="eyebrow">Verified order</div><div className="result-order">{refText(orderNumber || orderRef)}</div><div className="panel-sub">{refText(getValue(result.order, ['status', 'order_status']))}</div></div><Badge value={String(shipmentStatus || 'order found')} /></div>
        <div className="result-cards"><DataBox title="Order details" icon={<ShoppingBag size={14} />} value={result.order} /><DataBox title="Shipment" icon={<Truck size={14} />} value={result.shipment} /><DataBox title="Product" icon={<PackageCheck size={14} />} value={result.product} /><div className="result-box"><h3><CreditCard size={14} style={{ verticalAlign: 'middle', marginRight: 6 }} />Refund history</h3>{result.refunds?.length ? result.refunds.map((refund, index) => <div className="detail-line" key={index}><span className="detail-label">Refund {index + 1}</span><span className="detail-value">{refText(getValue(refund, ['amount', 'status', 'refund_id']) || JSON.stringify(refund))}</span></div>) : <div className="hint">No refunds recorded.</div>}</div></div>
      </> : <div className="error-state" style={{ marginTop: 5 }}><AlertCircle size={18} /><span>{result.message || 'No matching order was found for this customer.'}</span></div>}</div>}
    </div></section>
      <aside><section className="panel"><div className="panel-head"><h2 className="panel-title">Lookup guardrails</h2><ShieldCheck size={16} color="#5e9572" /></div><div className="panel-body"><div className="detail-line"><span className="detail-label">Ownership check</span><span className="detail-value">Required</span></div><div className="detail-line"><span className="detail-label">Refund history</span><span className="detail-value">Included</span></div><p className="queue-note">Use the customer reference supplied in the conversation. Order details stay scoped to the verified owner.</p></div></section></aside>
    </div>
  </div>;
}

function DataBox({ title, icon, value }: { title: string; icon: ReactNode; value: unknown }) {
  const entries = value && typeof value === 'object' ? Object.entries(value as Record<string, unknown>).filter(([, item]) => typeof item !== 'object') : [];
  return <div className="result-box"><h3>{icon} <span style={{ verticalAlign: 'middle', marginLeft: 5 }}>{title}</span></h3>{value ? entries.length ? entries.slice(0, 5).map(([key, item]) => <div className="detail-line" key={key}><span className="detail-label">{nice(key)}</span><span className="detail-value">{refText(item)}</span></div>) : <div className="hint">Details are available in the verified order record.</div> : <div className="hint">No details available.</div>}</div>;
}

function Policies() {
  const mutation = useAskShopSensePolicy();
  const [question, setQuestion] = useState('');
  const [order, setOrder] = useState('');
  const [customer, setCustomer] = useState('');
  const submit = (event: FormEvent) => { event.preventDefault(); if (question.trim()) mutation.mutate({ data: { question: question.trim(), order_id: order.trim() || undefined, customer_id: customer.trim() || undefined } }); };
  const answer = mutation.data;
  return <div className="page"><PageHeading eyebrow="Grounded answers · linked sources" title="Policy desk" intro="Find a clear answer, with the source material beside it." />
    <div className="policy-layout"><section className="panel"><div className="panel-head"><div><h2 className="panel-title">Ask about a policy</h2><div className="panel-sub">Be specific; add order or customer context if relevant.</div></div><BookOpen size={17} color="#5e9572" /></div><div className="panel-body"><form onSubmit={submit}><div className="form-row"><div className="field-group"><label className="field-label" htmlFor="policy-customer">Customer reference <span style={{ fontWeight: 400 }}>(optional)</span></label><input id="policy-customer" className="field" value={customer} onChange={(event) => setCustomer(event.target.value)} placeholder="Customer ID" data-testid="input-policy-customer" /></div><div className="field-group"><label className="field-label" htmlFor="policy-order">Order reference <span style={{ fontWeight: 400 }}>(optional)</span></label><input id="policy-order" className="field" value={order} onChange={(event) => setOrder(event.target.value)} placeholder="Order ID" data-testid="input-policy-order" /></div></div><div className="field-group"><label className="field-label" htmlFor="policy-question">Your policy question</label><textarea id="policy-question" className="textarea" value={question} onChange={(event) => setQuestion(event.target.value)} maxLength={5000} placeholder="What does our policy say about…" data-testid="input-policy-question" /></div><button className="button" disabled={!question.trim() || mutation.isPending} data-testid="button-ask-policy"><Search size={14} />{mutation.isPending ? 'Checking sources…' : 'Find policy answer'}</button></form>
      {mutation.isError && <div style={{ marginTop: 14 }}><ErrorState message="Policy sources could not be reached. Please retry." retry={() => mutation.mutate({ data: { question: question.trim(), order_id: order.trim() || undefined, customer_id: customer.trim() || undefined } })} /></div>}
      {answer && <div style={{ marginTop: 22 }} data-testid="policy-answer"><div className="eyebrow">Policy answer · {nice(answer.status)}</div><div className="answer-box">{answer.answer}</div>{answer.requires_human && <div className="error-state" style={{ marginTop: 11 }}><UserRound size={17} /><span>This question needs a human policy review before you make a commitment.</span></div>}</div>}
      {!answer && !mutation.isPending && <div style={{ marginTop: 23 }}><div className="eyebrow">A good question to start with</div><div className="hint">“Can this order be refunded after delivery?”</div></div>}
    </div></section><aside><section className="panel"><div className="panel-head"><div><h2 className="panel-title">Sources & evidence</h2><div className="panel-sub">{answer?.citations?.length || 0} citations</div></div><FileText size={16} color="#5e9572" /></div>
      <div className="panel-body">{answer?.citations?.length ? answer.citations.map((citation, index) => <div className="citation" key={`${citation.document_id}-${index}`}><span className="citation-num">{String(index + 1).padStart(2, '0')}</span><div><div className="citation-title">{citation.title}</div><div className="citation-source">{citation.source} · {citation.document_id}</div></div></div>) : answer ? <EmptyState icon={<FileText size={19} />} title="No citations returned" copy="Use human judgment when no source is attached to an answer." /> : <EmptyState icon={<BookOpen size={20} />} title="Grounded in your source library" copy="Ask a question to see the relevant policy passages and citations here." />}</div>
      {answer?.evidence?.length ? <div className="panel-body" style={{ borderTop: '1px solid #eeeae0' }}><div className="eyebrow">Evidence passages</div>{answer.evidence.map((evidence) => <div key={evidence.document_id} className="citation"><div><div className="citation-title">{evidence.title} <span className="ticket-id">· {evidence.score.toFixed(2)}</span></div><p className="hint" style={{ lineHeight: 1.6, margin: '5px 0 0' }}>{evidence.text}</p></div></div>)}</div> : null}
    </section></aside></div>
  </div>;
}

function Customer({ customerRef }: { customerRef: string }) {
  const memoryQuery = useGetCustomerMemory(customerRef, { query: { enabled: Boolean(customerRef) && customerRef !== 'lookup', queryKey: getGetCustomerMemoryQueryKey(customerRef) } });
  const update = useUpdateCustomerMemory();
  const client = useQueryClient();
  const [newPreference, setNewPreference] = useState('');
  const [lookupValue, setLookupValue] = useState('');
  const [editing, setEditing] = useState(false);
  const memory = memoryQuery.data;
  const preferences = memory?.preferences || [];
  const savePreferences = (next: string[]) => update.mutate({ customerRef, data: { preferences: next } }, {
    onSuccess: (saved) => {
      client.setQueryData(getGetCustomerMemoryQueryKey(customerRef), saved);
      client.invalidateQueries({ queryKey: getGetCustomerMemoryQueryKey(customerRef) });
      setNewPreference('');
    },
  });
  if (customerRef === 'lookup') return <div className="page"><PageHeading eyebrow="Customer care" title="Customer memory" intro="Look up persisted preferences and recent support history." /><section className="panel" style={{ maxWidth: 600 }}><div className="panel-head"><h2 className="panel-title">Find a customer</h2><Users size={17} color="#5e9572" /></div><div className="panel-body"><LookupCustomerForm onSubmit={(value) => setLookupValue(value)} value={lookupValue} /></div>{lookupValue.trim() && <div className="panel-body" style={{ borderTop: '1px solid #eeeae0' }}><Link className="button" href={`/customers/${encodeURIComponent(lookupValue.trim())}`}>Open customer profile <ArrowRight size={14} /></Link></div>}</section></div>;
  return <div className="page"><PageHeading eyebrow="Customer care" title="A little context goes a long way." intro="Keep useful preferences close, and carry the customer’s story forward." action={<Link href="/customers/lookup" className="button secondary"><Search size={14} /> Find another</Link>} />
    {memoryQuery.isLoading ? <LoadingCards count={2} /> : memoryQuery.isError ? <ErrorState message="Customer memory could not be loaded." retry={() => memoryQuery.refetch()} /> : memory && <>
      <div className="customer-hero"><div className="customer-avatar">{initials(customerRef)}</div><div><div className="panel-title">Customer profile</div><div className="customer-id">{memory.customer_id}</div></div><div style={{ marginLeft: 'auto' }}><Badge value="Care context" /></div></div>
      {update.isError && <div style={{ marginBottom: 14 }}><ErrorState message="Preference changes did not save." retry={() => update.reset()} /></div>}
      <div className="section-grid"><section className="panel"><div className="panel-head"><div><h2 className="panel-title">Support preferences</h2><div className="panel-sub">Explicit notes to make the next conversation more personal</div></div><button className="button secondary small" onClick={() => setEditing(!editing)} data-testid="button-edit-preferences">{editing ? 'Done' : 'Edit notes'}</button></div><div className="panel-body">
        {preferences.length ? preferences.map((preference, index) => <div className="pref-item" key={`${preference}-${index}`}><span className="pref-dot" /><span style={{ flex: 1 }}>{preference}</span>{editing && <button className="icon-button" aria-label={`Remove preference ${preference}`} onClick={() => savePreferences(preferences.filter((_, itemIndex) => itemIndex !== index))} data-testid={`button-remove-preference-${index}`}><X size={13} /></button>}</div>) : <EmptyState icon={<Sparkles size={19} />} title="No preferences saved yet" copy="Add a small detail that helps the next conversation feel more considered." />}
        {editing && <form className="preference-form" onSubmit={(event) => { event.preventDefault(); if (newPreference.trim() && preferences.length < 20) savePreferences([...preferences, newPreference.trim()]); }}><input className="field" value={newPreference} onChange={(event) => setNewPreference(event.target.value)} placeholder="Add a customer preference…" aria-label="New customer preference" data-testid="input-new-preference" /><button className="button small" disabled={!newPreference.trim() || update.isPending || preferences.length >= 20} data-testid="button-add-preference"><Check size={13} /> Save</button></form>}
        {editing && <p className="hint" style={{ margin: '10px 0 0' }}>Up to 20 preferences. Changes are saved to customer memory.</p>}
      </div></section><section className="panel"><div className="panel-head"><div><h2 className="panel-title">Recent tickets</h2><div className="panel-sub">A short history of support touchpoints</div></div><MessageSquareText size={16} color="#5e9572" /></div><div className="panel-body">{memory.recent_tickets?.length ? <div className="ticket-list">{memory.recent_tickets.map((ticket) => <TicketRow ticket={ticket} key={ticket.ticket_id} />)}</div> : <EmptyState icon={<Inbox size={19} />} title="No recent support history" copy="Past tickets will appear here as this customer contacts the team." />}</div></section></div>
    </>}
  </div>;
}

function LookupCustomerForm({ onSubmit, value }: { onSubmit: (value: string) => void; value: string }) {
  const [input, setInput] = useState(value);
  return <form onSubmit={(event) => { event.preventDefault(); onSubmit(input); }}><label className="field-label" htmlFor="customer-lookup">Customer reference</label><div style={{ display: 'flex', gap: 9 }}><input id="customer-lookup" className="field" value={input} onChange={(event) => setInput(event.target.value)} placeholder="Enter customer ID" required data-testid="input-customer-reference" /><button className="button" data-testid="button-find-customer"><Search size={14} /> Find</button></div></form>;
}

function RoutedPages() {
  return <AppShell notify={() => undefined}><Switch>
    <Route path="/" component={Dashboard} />
    <Route path="/tickets" component={Tickets} />
    <Route path="/reviews" component={Reviews} />
    <Route path="/orders" component={Orders} />
    <Route path="/policies" component={Policies} />
    <Route path="/customers/lookup"><Customer customerRef="lookup" /></Route>
    <Route path="/customers/:customerRef">{(params) => <Customer customerRef={decodeURIComponent(params.customerRef || '')} />}</Route>
    <Route component={NotFound} />
  </Switch></AppShell>;
}

function App() {
  return <QueryClientProvider client={queryClient}><Router base="/shopsense"><RoutedPages /></Router></QueryClientProvider>;
}

export default App;
