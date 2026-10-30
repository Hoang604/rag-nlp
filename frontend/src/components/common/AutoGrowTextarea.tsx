import React, { useCallback, useEffect, useLayoutEffect, useRef } from 'react';

type AutoGrowTextareaProps = Omit<
  React.TextareaHTMLAttributes<HTMLTextAreaElement>,
  'value' | 'onChange' | 'rows'
> & {
  value: string;
  onValueChange: (value: string) => void;
  onSubmit: () => void;
};

export const AutoGrowTextarea: React.FC<AutoGrowTextareaProps> = ({
  value,
  onValueChange,
  onSubmit,
  className = '',
  ...rest
}) => {
  const ref = useRef<HTMLTextAreaElement>(null);

  const fitHeight = useCallback(() => {
    const element = ref.current;
    if (!element) return;
    element.style.height = 'auto';
    element.style.height = `${element.scrollHeight}px`;
  }, []);

  useLayoutEffect(fitHeight, [value, fitHeight]);

  useEffect(() => {
    window.addEventListener('resize', fitHeight);
    return () => window.removeEventListener('resize', fitHeight);
  }, [fitHeight]);

  return (
    <textarea
      ref={ref}
      rows={1}
      value={value}
      onChange={(e) => onValueChange(e.target.value)}
      onKeyDown={(e) => {
        if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
          e.preventDefault();
          onSubmit();
        }
      }}
      className={`block max-h-64 resize-none overflow-y-auto ${className}`}
      {...rest}
    />
  );
};
