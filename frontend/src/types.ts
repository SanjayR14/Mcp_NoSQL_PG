export interface DbNode {
  name: string;
  type: 'database' | 'schema' | 'table' | 'column';
  children?: DbNode[];
}

export interface ConnectionDetails {
  host: string;
  port: string;
  user: string;
  password: string;
  database: string;
  ssl: boolean;
}