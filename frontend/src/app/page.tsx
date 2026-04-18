/* ─────────────────────────────────────────────────────────────
   Home Page — src/app/page.tsx

   This is the root page rendered at localhost:3000.
   Its only job is to mount the ChatShell component.
   All the real UI logic lives inside ChatShell.
─────────────────────────────────────────────────────────────── */

import ChatShell from "@/components/ChatShell";

export default function Home() {
  return <ChatShell />;
}
