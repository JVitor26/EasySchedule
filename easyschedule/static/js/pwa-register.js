if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/service-worker.js').catch(() => {
      // Registro opcional: falhas nao podem quebrar a aplicacao.
    });
  });
}
