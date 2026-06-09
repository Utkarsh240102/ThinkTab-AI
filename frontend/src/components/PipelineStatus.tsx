
import StatusBubble from "./StatusBubble";
import ErrorBubble from "./ErrorBubble";

interface PipelineStatusProps {
  isLoading: boolean;
  statusText: string;
  error: string | null;
  onRetry: () => void;
}

export default function PipelineStatus({
  isLoading,
  statusText,
  error,
  onRetry,
}: PipelineStatusProps) {
  if (error) {
    return <ErrorBubble message={error} onRetry={onRetry} />;
  }

  if (isLoading && statusText) {
    return <StatusBubble text={statusText} />;
  }

  return null;
}
