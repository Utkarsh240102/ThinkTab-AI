import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";

interface TypewriterMarkdownProps {
  text: string;
  enabled: boolean;
  speedMs?: number;
  onDone?: () => void;
}

export default function TypewriterMarkdown({
  text,
  enabled,
  speedMs = 12,
  onDone,
}: TypewriterMarkdownProps) {
  const [displayedText, setDisplayedText] = useState("");
  const onDoneRef = useRef(onDone);

  useEffect(() => {
    onDoneRef.current = onDone;
  }, [onDone]);

  useEffect(() => {
    if (!enabled) return;

    let index = 0;
    let timeoutId: ReturnType<typeof setTimeout> | undefined;
    let cancelled = false;

    function revealNextCharacter() {
      if (cancelled) return;

      index += 1;
      setDisplayedText(text.slice(0, index));

      if (index < text.length) {
        timeoutId = setTimeout(revealNextCharacter, speedMs);
      } else {
        onDoneRef.current?.();
      }
    }

    timeoutId = setTimeout(revealNextCharacter, speedMs);

    return () => {
      cancelled = true;
      if (timeoutId) clearTimeout(timeoutId);
    };
  }, [enabled, speedMs, text]);

  return <ReactMarkdown>{enabled ? displayedText : text}</ReactMarkdown>;
}
