interface GeneratedSymbolPreviewProps {
  title: string;
  symbols: string[];
}

export function GeneratedSymbolPreview({ title, symbols }: GeneratedSymbolPreviewProps) {
  return (
    <div className="generated-symbol-preview">
      <span className="generated-symbol-preview__title">{title}</span>
      <div className="generated-symbol-preview__list">
        {symbols.map((symbol) => (
          <span key={symbol} className="generated-symbol-preview__symbol">
            {symbol}
          </span>
        ))}
      </div>
    </div>
  );
}