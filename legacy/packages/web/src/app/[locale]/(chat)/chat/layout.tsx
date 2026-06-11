/**
 * Chat Page Layout
 * Separate route group from (public) — no Header, no Footer, no FloatingChatbot.
 * Full viewport height for immersive chat-first experience.
 */

export default function ChatLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="h-screen flex flex-col overflow-hidden bg-background">
      {children}
    </div>
  );
}
