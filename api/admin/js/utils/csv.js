export default function exportAsCSV(header = [], rows = [], name = 'file.csv') {
  if (!rows.length) {
    return;
  }

  let csv = header.length ? `${header.join(',')}\n` : `${','.repeat(rows[0].length)}\n`;

  rows.forEach((row) => {
    csv += `${row.join(',')}\n`;
  });

  const hiddenDownloader = document.createElement('a');
  hiddenDownloader.href = `data:text/csv;charset=utf-8,${encodeURI(csv)}`;
  hiddenDownloader.target = '_blank';
  hiddenDownloader.download = name;
  hiddenDownloader.click();
}
