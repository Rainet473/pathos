import FakePresentationApp from "./presentation/FakePresentationApp";
import ProbeApp from "./probe/ProbeApp";
import LiveConversationApp from "./live/LiveConversationApp";

export default function App() {
  if (window.location.pathname === "/probe") return <ProbeApp />;
  if (window.location.pathname === "/live") return <LiveConversationApp />;
  return <FakePresentationApp />;
}
