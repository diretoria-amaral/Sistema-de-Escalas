interface PlaceholderPageProps {
  title: string;
  description: string;
  section: string;
}

function PlaceholderPage({ title, description, section }: PlaceholderPageProps) {
  return (
    <div className="card">
      <div className="placeholder-header">
        <span className="placeholder-section">{section}</span>
        <h2>{title}</h2>
      </div>
      
      <div className="placeholder-content">
        <div className="placeholder-icon">🚧</div>
        <h3>Em Desenvolvimento</h3>
        <p>{description}</p>
        <p className="placeholder-note">
          Esta funcionalidade estara disponivel em breve.
        </p>
      </div>
    </div>
  );
}

export default PlaceholderPage;
