import { wsUrl } from "@/lib/api";

type TrackerEvent = Record<string, unknown> & { event_type: string };

export class BehaviorTracker {
  private socket: WebSocket | null = null;
  private lastMouseAt = 0;
  private lastMouse: { x: number; y: number; ts: number } | null = null;
  private lastScroll = { y: 0, ts: Date.now() };
  private idleTimer: number | null = null;
  private idleStartedAt: number | null = null;
  private observer: IntersectionObserver | null = null;
  private sectionEnter = new Map<string, number>();
  private hoverEnter = new Map<string, number>();
  private disposers: Array<() => void> = [];

  constructor(
    private sessionId: number,
    private token: string,
    private root: HTMLElement
  ) {}

  start() {
    this.socket = new WebSocket(wsUrl(`/track/${this.sessionId}`, this.token));
    this.socket.addEventListener("open", () => this.send({ event_type: "heartbeat_open" }));
    this.bindSectionObserver();
    this.bindMouse();
    this.bindScroll();
    this.bindSelection();
    this.bindClicks();
    this.bindIdle();
  }

  stop() {
    this.flushSectionExits();
    for (const dispose of this.disposers) dispose();
    this.disposers = [];
    this.observer?.disconnect();
    this.socket?.close();
  }

  send(data: TrackerEvent) {
    if (this.socket?.readyState !== WebSocket.OPEN) return;
    this.socket.send(JSON.stringify({ type: "event", data, ts: Date.now() }));
  }

  private bindSectionObserver() {
    const sections = Array.from(this.root.querySelectorAll<HTMLElement>("[data-section-id]"));
    this.observer = new IntersectionObserver(
      entries => {
        for (const entry of entries) {
          const sectionId = entry.target.getAttribute("data-section-id");
          if (!sectionId) continue;
          if (entry.isIntersecting) {
            this.sectionEnter.set(sectionId, Date.now());
            this.send({ event_type: "section_view", section_id: sectionId, timestamp: Date.now() });
          } else {
            const enteredAt = this.sectionEnter.get(sectionId);
            if (enteredAt) {
              this.send({ event_type: "section_exit", section_id: sectionId, time_spent_ms: Date.now() - enteredAt });
              this.sectionEnter.delete(sectionId);
            }
          }
        }
      },
      { threshold: 0.45 }
    );
    for (const section of sections) this.observer.observe(section);
  }

  private bindMouse() {
    const onMove = (event: MouseEvent) => {
      const now = Date.now();
      if (now - this.lastMouseAt < 500) return;
      const velocity = this.lastMouse ? Math.hypot(event.clientX - this.lastMouse.x, event.clientY - this.lastMouse.y) / Math.max(now - this.lastMouse.ts, 1) : 0;
      this.lastMouseAt = now;
      this.lastMouse = { x: event.clientX, y: event.clientY, ts: now };
      this.send({ event_type: "mouse_move", x: event.clientX, y: event.clientY, velocity });
      this.noteActivity();
    };
    const onOver = (event: MouseEvent) => {
      const target = event.target as HTMLElement;
      const elementId = target.id || target.getAttribute("data-section-id") || target.tagName.toLowerCase();
      this.hoverEnter.set(elementId, Date.now());
      this.send({ event_type: "hover_start", element_id: elementId, x: event.clientX, y: event.clientY });
      this.noteActivity();
    };
    const onOut = (event: MouseEvent) => {
      const target = event.target as HTMLElement;
      const elementId = target.id || target.getAttribute("data-section-id") || target.tagName.toLowerCase();
      const startedAt = this.hoverEnter.get(elementId);
      if (!startedAt) return;
      this.hoverEnter.delete(elementId);
      this.send({ event_type: "hover_end", element_id: elementId, x: event.clientX, y: event.clientY, duration_ms: Date.now() - startedAt });
      this.noteActivity();
    };
    window.addEventListener("mousemove", onMove);
    this.root.addEventListener("mouseover", onOver);
    this.root.addEventListener("mouseout", onOut);
    this.disposers.push(() => window.removeEventListener("mousemove", onMove));
    this.disposers.push(() => this.root.removeEventListener("mouseover", onOver));
    this.disposers.push(() => this.root.removeEventListener("mouseout", onOut));
  }

  private bindScroll() {
    const onScroll = () => {
      const now = Date.now();
      const y = window.scrollY;
      const delta = y - this.lastScroll.y;
      const maxScroll = Math.max(document.documentElement.scrollHeight - window.innerHeight, 1);
      const velocity = Math.abs(delta) / Math.max(now - this.lastScroll.ts, 1);
      this.lastScroll = { y, ts: now };
      this.send({
        event_type: "scroll",
        direction: delta < 0 ? "up" : "down",
        position: Math.round((y / maxScroll) * 100),
        velocity
      });
      this.noteActivity();
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    this.disposers.push(() => window.removeEventListener("scroll", onScroll));
  }

  private bindSelection() {
    const onSelection = () => {
      const text = window.getSelection()?.toString() || "";
      if (!text.trim()) return;
      const node = window.getSelection()?.anchorNode?.parentElement;
      const section = node?.closest<HTMLElement>("[data-section-id]");
      this.send({ event_type: "text_select", section_id: section?.dataset.sectionId, char_count: text.length });
      this.noteActivity();
    };
    document.addEventListener("selectionchange", onSelection);
    this.disposers.push(() => document.removeEventListener("selectionchange", onSelection));
  }

  private bindClicks() {
    const onClick = (event: MouseEvent) => {
      const target = event.target as HTMLElement;
      this.send({ event_type: "click", element_type: target.tagName.toLowerCase(), x: event.clientX, y: event.clientY });
      this.noteActivity();
    };
    this.root.addEventListener("click", onClick);
    this.disposers.push(() => this.root.removeEventListener("click", onClick));
  }

  private bindIdle() {
    const startIdleTimer = () => {
      if (this.idleTimer) window.clearTimeout(this.idleTimer);
      this.idleTimer = window.setTimeout(() => {
        this.idleStartedAt = Date.now();
        this.send({ event_type: "idle_start" });
      }, 30000);
    };
    this.noteActivity = () => {
      if (this.idleStartedAt) {
        this.send({ event_type: "idle_end", duration_ms: Date.now() - this.idleStartedAt });
        this.idleStartedAt = null;
      }
      startIdleTimer();
    };
    startIdleTimer();
    this.disposers.push(() => {
      if (this.idleTimer) window.clearTimeout(this.idleTimer);
    });
  }

  private noteActivity() {}

  private flushSectionExits() {
    const now = Date.now();
    for (const [elementId, enteredAt] of this.hoverEnter.entries()) {
      this.send({ event_type: "hover_end", element_id: elementId, duration_ms: now - enteredAt });
    }
    this.hoverEnter.clear();
    for (const [sectionId, enteredAt] of this.sectionEnter.entries()) {
      this.send({ event_type: "section_exit", section_id: sectionId, time_spent_ms: now - enteredAt });
    }
    this.sectionEnter.clear();
  }
}
