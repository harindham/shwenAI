export type Provider = "postgresql" | "supabase" | "mysql" | "mariadb" | "other";

export type DatabaseObject = {
  name: string;
  kind: "table" | "view";
  columns: {
    name: string;
    type: string;
    nullable: boolean | null;
    default: string | null;
    comment: string | null;
  }[];
  primary_key: string[];
  foreign_keys: {
    name: string | null;
    columns: string[];
    referenced_schema: string | null;
    referenced_table: string | null;
    referenced_columns: string[];
  }[];
  indexes: { name: string | null; columns: string[]; unique: boolean }[];
  unique_constraints: { name: string | null; columns: string[] }[];
  check_constraints: { name: string | null; sql: string | null }[];
  definition?: string | null;
};

export type DatabaseMetadata = {
  connected: boolean;
  provider: Provider;
  database: string;
  schema: string;
  connection_name: string;
  summary: { schemas: number; tables_and_views: number; columns: number };
  stored_metadata_items: number;
  schemas: { name: string; sequences: string[]; objects: DatabaseObject[] }[];
};

export type DatabaseConnectionDetails = {
  provider: Provider;
  connection_name: string;
  host: string;
  port: number;
  database: string;
  schema: string;
  username: string;
  password: string;
  dialect: string | null;
};
