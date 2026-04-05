type RecordButtonProps = {
  isRecording: boolean;
  onClick: () => void;
  disabled?: boolean;
};

export function RecordButton({ isRecording, onClick, disabled }: RecordButtonProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={`record-btn ${isRecording ? "recording" : "idle"}`}
    >
      {isRecording ? "Stop" : "Record"}
    </button>
  );
}
