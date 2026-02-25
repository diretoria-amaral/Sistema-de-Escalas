import { useState, useRef, useEffect } from 'react';

interface ExpandableTextProps {
  text: string;
  maxLines?: number;
  defaultExpanded?: boolean;
}

export function ExpandableText({ 
  text, 
  maxLines = 3, 
  defaultExpanded = false 
}: ExpandableTextProps) {
  const [expanded, setExpanded] = useState(defaultExpanded);
  const [needsExpansion, setNeedsExpansion] = useState(false);
  const textRef = useRef<HTMLDivElement>(null);
  const measureRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (measureRef.current && textRef.current) {
      const lineHeight = parseFloat(getComputedStyle(textRef.current).lineHeight) || 20;
      const maxHeight = lineHeight * maxLines;
      const actualHeight = measureRef.current.scrollHeight;
      setNeedsExpansion(actualHeight > maxHeight + 2);
    }
  }, [text, maxLines]);

  const collapsedStyle: React.CSSProperties = {
    whiteSpace: 'pre-wrap',
    wordBreak: 'break-word',
    overflow: 'hidden',
    display: '-webkit-box',
    WebkitLineClamp: maxLines,
    WebkitBoxOrient: 'vertical' as const,
    lineHeight: '1.5',
  };

  const expandedStyle: React.CSSProperties = {
    whiteSpace: 'pre-wrap',
    wordBreak: 'break-word',
    lineHeight: '1.5',
  };

  const measureStyle: React.CSSProperties = {
    position: 'absolute',
    visibility: 'hidden',
    whiteSpace: 'pre-wrap',
    wordBreak: 'break-word',
    lineHeight: '1.5',
    width: '100%',
    pointerEvents: 'none',
  };

  return (
    <div style={{ position: 'relative' }}>
      <div 
        ref={measureRef} 
        style={measureStyle}
        aria-hidden="true"
      >
        {text}
      </div>
      <div 
        ref={textRef}
        style={expanded ? expandedStyle : collapsedStyle}
      >
        {text}
      </div>
      {needsExpansion && (
        <button
          onClick={(e) => {
            e.stopPropagation();
            setExpanded(!expanded);
          }}
          style={{
            background: 'none',
            border: 'none',
            color: '#2563eb',
            cursor: 'pointer',
            padding: '4px 0',
            fontSize: '0.85rem',
            fontWeight: 500,
          }}
        >
          {expanded ? 'Ver menos' : 'Ver mais'}
        </button>
      )}
    </div>
  );
}

export default ExpandableText;
