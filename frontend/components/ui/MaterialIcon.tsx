interface MaterialIconProps {
  name: string;
  filled?: boolean;
  className?: string;
}

export default function MaterialIcon({ name, filled, className = "" }: MaterialIconProps) {
  return (
    <span
      className={`material-symbols-outlined ${className}`}
      style={filled ? { fontVariationSettings: "'FILL' 1" } : undefined}
    >
      {name}
    </span>
  );
}
