import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// `npm run dev` serves the desk on http://localhost:5173 and opens it in the browser.
// The page calls the FastAPI backend directly at http://localhost:8000 (CORS allows :5173).
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, open: true },
});
