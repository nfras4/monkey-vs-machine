declare global {
  namespace App {
    interface Platform {
      env: {
        DB: D1Database;
        MVM_INGEST_TOKEN: string;
        PUBLISH_SCHEMA_VERSION: string;
      };
    }
  }
}

export {};
