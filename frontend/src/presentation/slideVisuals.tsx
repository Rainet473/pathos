import type { ReactNode } from "react";

export type SlideVisualKind =
  | "control-loop"
  | "clutch-coupling"
  | "power-path"
  | "reverse-load"
  | "speed-match"
  | "abs-feedback"
  | "generic-flow";

export interface SlideVisualSpec {
  id: string;
  kind: SlideVisualKind;
  nodes: string[];
}

const VISUALS: Record<string, Omit<SlideVisualSpec, "id">> = {
  "control-loop": {
    kind: "control-loop",
    nodes: ["Rider input", "Drivetrain + brakes", "Tyre force", "Feedback"],
  },
  "clutch-and-gears": {
    kind: "clutch-coupling",
    nodes: ["Engine", "Clutch", "Gearbox", "Rear wheel"],
  },
  "power-to-wheel": {
    kind: "power-path",
    nodes: ["Combustion", "Clutch", "Gear ratio", "Final drive", "Wheel"],
  },
  "engine-braking": {
    kind: "reverse-load",
    nodes: ["Rear wheel", "Gear ratio", "Engine resistance"],
  },
  "rev-matching": {
    kind: "speed-match",
    nodes: ["Current RPM", "Throttle blip", "Lower-gear target"],
  },
  "braking-abs": {
    kind: "abs-feedback",
    nodes: ["Brake input", "Pressure", "Tyre force", "Wheel sensor"],
  },
};

export function visualSpecForSlide(slideId: string): SlideVisualSpec {
  const visual = VISUALS[slideId];
  return visual
    ? { id: slideId, ...visual }
    : { id: slideId, kind: "generic-flow", nodes: ["Input", "System", "Response"] };
}

function ArrowDefs() {
  return (
    <defs>
      <marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
        <path d="M0,0 L8,4 L0,8 Z" className="diagram-arrow-head" />
      </marker>
    </defs>
  );
}

function Node({ x, y, width, children, accent = false }: { x: number; y: number; width: number; children: ReactNode; accent?: boolean }) {
  return (
    <g className={accent ? "diagram-node diagram-node-accent" : "diagram-node"}>
      <rect x={x} y={y} width={width} height="46" rx="14" />
      <text x={x + width / 2} y={y + 28} textAnchor="middle">{children}</text>
    </g>
  );
}

function SlideDiagramContent({ spec }: { spec: SlideVisualSpec }) {
  switch (spec.kind) {
    case "control-loop":
      return (
        <>
          <path className="diagram-link" d="M205 50 H505 Q550 50 550 92 V104" />
          <path className="diagram-link" d="M515 140 H215 Q170 140 170 98 V86" />
          <Node x={50} y={27} width={155} accent>{spec.nodes[0]}</Node>
          <Node x={505} y={27} width={165}>{spec.nodes[1]}</Node>
          <Node x={485} y={117} width={145} accent>{spec.nodes[2]}</Node>
          <Node x={50} y={117} width={165}>{spec.nodes[3]}</Node>
        </>
      );
    case "clutch-coupling":
      return (
        <>
          <path className="diagram-link" d="M145 96 H245 M357 96 H452 M557 96 H635" />
          <circle className="diagram-machine" cx="88" cy="96" r="50" />
          <text className="diagram-machine-label" x="88" y="101" textAnchor="middle">{spec.nodes[0]}</text>
          <g className="diagram-clutch">
            <circle cx="274" cy="96" r="38" /><circle cx="294" cy="96" r="38" /><circle cx="314" cy="96" r="38" />
          </g>
          <text className="diagram-caption" x="294" y="160" textAnchor="middle">{spec.nodes[1]}</text>
          <g className="diagram-gears"><circle cx="476" cy="83" r="31" /><circle cx="524" cy="111" r="25" /></g>
          <text className="diagram-caption" x="500" y="160" textAnchor="middle">{spec.nodes[2]}</text>
          <circle className="diagram-wheel" cx="665" cy="96" r="54" />
          <circle className="diagram-wheel-hub" cx="665" cy="96" r="15" />
          <text className="diagram-caption" x="665" y="170" textAnchor="middle">{spec.nodes[3]}</text>
        </>
      );
    case "power-path":
      return (
        <>
          <path className="diagram-link" d="M130 96 H166 M270 96 H305 M409 96 H444 M548 96 H585" />
          {spec.nodes.map((label, index) => (
            <Node key={label} x={index * 139 + 12} y={73} width={118} accent={index === 0 || index === 4}>{label}</Node>
          ))}
          <path className="diagram-energy" d="M18 45 H697" />
          <text className="diagram-caption" x="357" y="28" textAnchor="middle">Torque path</text>
        </>
      );
    case "reverse-load":
      return (
        <>
          <path className="diagram-link diagram-link-reverse" d="M585 96 H155" />
          <Node x={535} y={73} width={150} accent>{spec.nodes[0]}</Node>
          <Node x={286} y={73} width={145}>{spec.nodes[1]}</Node>
          <Node x={35} y={73} width={180} accent>{spec.nodes[2]}</Node>
          <path className="diagram-throttle" d="M78 45 H179" />
          <text className="diagram-caption" x="128" y="27" textAnchor="middle">Throttle closed</text>
          <text className="diagram-caption" x="360" y="153" textAnchor="middle">Wheel drives a resisting engine</text>
        </>
      );
    case "speed-match":
      return (
        <>
          <path className="diagram-axis" d="M55 25 V155 H680" />
          <path className="diagram-target" d="M70 58 H670" />
          <path className="diagram-speed" d="M70 135 C230 135 275 130 345 92 S470 58 670 58" />
          <circle className="diagram-focus" cx="350" cy="89" r="8" />
          <text className="diagram-caption" x="177" y="128">{spec.nodes[0]}</text>
          <text className="diagram-caption diagram-caption-accent" x="350" y="75" textAnchor="middle">{spec.nodes[1]}</text>
          <text className="diagram-caption" x="540" y="45">{spec.nodes[2]}</text>
        </>
      );
    case "abs-feedback":
      return (
        <>
          <path className="diagram-link" d="M144 75 H198 M326 75 H380 M508 75 H570" />
          <Node x={20} y={52} width={124}>{spec.nodes[0]}</Node>
          <Node x={198} y={52} width={128}>{spec.nodes[1]}</Node>
          <Node x={380} y={52} width={128} accent>{spec.nodes[2]}</Node>
          <circle className="diagram-wheel" cx="625" cy="75" r="48" />
          <circle className="diagram-wheel-hub" cx="625" cy="75" r="14" />
          <path className="diagram-feedback" d="M625 126 V155 H326 V105" />
          <Node x={470} y={132} width={130}>{spec.nodes[3]}</Node>
        </>
      );
    default:
      return (
        <>
          <path className="diagram-link" d="M180 96 H280 M440 96 H540" />
          {spec.nodes.map((label, index) => <Node key={label} x={index * 265 + 10} y={73} width={170}>{label}</Node>)}
        </>
      );
  }
}

export function SlideVisual({ slideId, description }: { slideId: string; description: string }) {
  const spec = visualSpecForSlide(slideId);
  return (
    <figure className="slide-visual">
      <svg viewBox="0 0 720 190" role="img" aria-label={description} data-visual-kind={spec.kind}>
        <ArrowDefs />
        <SlideDiagramContent spec={spec} />
      </svg>
    </figure>
  );
}
