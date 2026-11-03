// Roteador mínimo: lê a URL e avisa o React quando ela muda.
import { useEffect, useState } from "react";

export function navigate(path) {
  history.pushState(null, "", path);
  window.dispatchEvent(new PopStateEvent("popstate"));
}

export function usePath() {
  const [path, setPath] = useState(location.pathname);
  useEffect(() => {
    const onChange = () => setPath(location.pathname);
    window.addEventListener("popstate", onChange);
    return () => window.removeEventListener("popstate", onChange);
  }, []);
  return path;
}

// Link que troca de tela sem recarregar a página.
export function Link({ to, children, ...rest }) {
  return (
    <a href={to} {...rest} onClick={(e) => { e.preventDefault(); navigate(to); }}>
      {children}
    </a>
  );
}
