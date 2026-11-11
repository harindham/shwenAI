import type { DatabaseMetadata, DatabaseObject } from "@/types/database";
import { DatabaseGlyph } from "@/components/database-icons";

type MetadataViewProps = {
  metadata: DatabaseMetadata;
};

export function MetadataView({ metadata }: MetadataViewProps) {
  return (
    <section className="metadata-panel" aria-labelledby="metadata-title">
      <div className="metadata-heading">
        <div>
          <div className="metadata-kicker"><span /> CONNECTION SUCCESSFUL</div>
          <h2 id="metadata-title">Database metadata</h2>
          <p>Schema <strong>{metadata.schema}</strong> fetched from <strong>{metadata.connection_name}</strong>.</p>
        </div>
        <span className="metadata-provider">{metadata.provider === "supabase" ? "Supabase · PostgreSQL" : metadata.provider}</span>
      </div>

      <div className="metadata-stats">
        <div><strong>{metadata.summary.schemas}</strong><span>Schemas</span></div>
        <div><strong>{metadata.summary.tables_and_views}</strong><span>Tables &amp; views</span></div>
        <div><strong>{metadata.summary.columns}</strong><span>Columns</span></div>
      </div>

      {metadata.schemas.length === 0 || metadata.summary.tables_and_views === 0
        ? <div className="metadata-empty">The connection succeeded, but no accessible tables or views were found in schema “{metadata.schema}”. Check the schema name and database user permissions.</div>
        : <div className="schema-list">{metadata.schemas.map((schema) => <SchemaSection key={schema.name} schema={schema} />)}</div>}
    </section>
  );
}

function SchemaSection({ schema }: { schema: DatabaseMetadata["schemas"][number] }) {
  return (
    <section className="schema-section">
      <h3><DatabaseGlyph />{schema.name}<span>{schema.objects.length} objects · {schema.sequences.length} sequences</span></h3>
      <div className="object-list">{schema.objects.map((object) => <ObjectDetails key={`${schema.name}.${object.kind}.${object.name}`} object={object} />)}</div>
      {schema.sequences.length > 0 && <div className="constraint-list schema-sequences"><h4>Sequences</h4>{schema.sequences.map((sequence) => <p key={sequence}>{sequence}</p>)}</div>}
    </section>
  );
}

function ObjectDetails({ object }: { object: DatabaseObject }) {
  return (
    <details className="object-details">
      <summary>
        <span className="object-kind">{object.kind === "view" ? "V" : "T"}</span>
        <strong>{object.name}</strong>
        <span className="object-count">{object.columns.length} columns</span>
        <svg viewBox="0 0 20 20" aria-hidden="true"><path d="m5 7.5 5 5 5-5" /></svg>
      </summary>
      <div className="object-body">
        <div className="column-header"><span>Column</span><span>Type</span><span>Details</span></div>
        {object.columns.map((column) => (
          <div className="column-row" key={column.name}>
            <strong>{column.name}</strong>
            <code>{column.type}</code>
            <span>
              {object.primary_key.includes(column.name) ? <em>PRIMARY KEY</em> : !column.nullable ? <em>NOT NULL</em> : "Nullable"}
              {column.default && <small>Default: {column.default}</small>}
              {column.comment && <small>{column.comment}</small>}
            </span>
          </div>
        ))}
        <ConstraintList title="Foreign keys" items={object.foreign_keys.map((key, index) => ({
          key: `${key.name ?? "fk"}-${index}`,
          text: `${key.columns.join(", ")} → ${key.referenced_schema ? `${key.referenced_schema}.` : ""}${key.referenced_table} (${key.referenced_columns.join(", ")})`,
        }))} />
        <ConstraintList title="Indexes" items={object.indexes.map((index, item) => ({
          key: `${index.name ?? "index"}-${item}`,
          text: `${index.name ?? "Index"}: ${index.columns.join(", ")}${index.unique ? " · unique" : ""}`,
        }))} />
        <ConstraintList title="Unique constraints" items={object.unique_constraints.map((constraint, index) => ({
          key: `${constraint.name ?? "unique"}-${index}`,
          text: `${constraint.name ?? "Unique"}: ${constraint.columns.join(", ")}`,
        }))} />
        <ConstraintList title="Check constraints" items={object.check_constraints.map((constraint, index) => ({
          key: `${constraint.name ?? "check"}-${index}`,
          text: `${constraint.name ?? "Check"}: ${constraint.sql}`,
        }))} />
        {object.definition && <pre className="view-definition">{object.definition}</pre>}
      </div>
    </details>
  );
}

function ConstraintList({ title, items }: { title: string; items: { key: string; text: string }[] }) {
  if (items.length === 0) return null;
  return <div className="constraint-list"><h4>{title}</h4>{items.map((item) => <p key={item.key}>{item.text}</p>)}</div>;
}
