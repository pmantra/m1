import hotkeys from 'hotkeys-js';

export default function attachFastFind() {
  const timeout = 300;
  let lastKey = null;

  hotkeys('f', (event, handler) => {
    event.preventDefault();

    if (handler.key === 'f' && lastKey === 'f') {
      lastKey = null;
      const query = prompt("Type in a practitioner or member's email");
      if (query) {
        window.open(`/admin/fastfind?q=${encodeURIComponent(query)}`);
      }
    } else {
      lastKey = 'f';
      setTimeout(() => {
        lastKey = null;
      }, timeout);
    }
  });
}
