/// <reference types="vite/client" />

// Allow side-effect CSS imports (import './Component.css')
declare module '*.css' {
  const styles: Record<string, string>;
  export default styles;
}
