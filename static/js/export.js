'use strict';

/*
 * Reusable CSV and PDF export helpers.
 *
 * Usage:
 *  exportToCsv(rows, columns, filename)
 *  exportToPdf(rows, columns, title, filename)
 *
 * Parameters:
 *  rows - array of plain objects e.g. [{ id:1, name:'Alpha', ... }]
 *  columns - array of { key, label } e.g. [{ key:'name', label:'Name', ... }]
 *  title - string show as the PDF heading
 *  filename - base name without extension e.g., 'delivery_teams_2025-01-01'
 */

/* CSV Export */
export function exportToCsv(rows, columns, filename) {
    // Header row
    const header = columns.map(c => csvCell(c.label)).join(',');

    // Data rows
    const body = rows.map(row =>
        columns.map(c => csvCell(row[c.key] ?? '')).join(',')
    );

    const csv  = [header, ...body].join('\r\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    triggerDownload(blob, `${filename}.csv`);
}

/* PDF Export — uses jsPDF (loaded from CDN in the template) */
export function exportToPdf(rows, columns, title, filename) {
    if (typeof window.jspdf === 'undefined') {
        console.error('exportToPdf: jsPDF is not loaded. Add the jsPDF CDN script to your template.');
        return;
    }

    const { jsPDF } = window.jspdf;
    const doc       = new jsPDF({ orientation: 'landscape', unit: 'pt', format: 'a4' });

    // Title
    doc.setFontSize(14);
    doc.setFont('helvetica', 'bold');
    doc.text(title, 40, 40);

    // Timestamp
    doc.setFontSize(9);
    doc.setFont('helvetica', 'normal');
    doc.setTextColor(120);
    doc.text(`Exported: ${new Date().toLocaleString()}`, 40, 56);
    doc.setTextColor(0);

    // Table via jsPDF-AutoTable
    if (typeof doc.autoTable === 'undefined') {
        console.error('exportToPdf: jsPDF-AutoTable plugin is not loaded.');
        return;
    }

    const pageW     = doc.internal.pageSize.getWidth();
    const pageH     = doc.internal.pageSize.getHeight();
    const sourceUrl = window.location.href;
    const appName   = 'Resource Planner';

    doc.autoTable({
        startY:     70,
        head:       [columns.map(c => c.label)],
        body:       rows.map(row => columns.map(c => formatPdfCell(row[c.key]))),
        styles:     { fontSize: 9, cellPadding: 6 },
        headStyles: { fillColor: [30, 30, 30], textColor: 255, fontStyle: 'bold' },
        alternateRowStyles: { fillColor: [247, 247, 247] },
        margin:     { left: 40, right: 40 },

        // Header and footer drawn on every page
        didDrawPage(pageData) {
            const pageNum   = pageData.pageNumber;
            const pageCount = doc.internal.getNumberOfPages();

            // ── Header ──────────────────────────────────────────────────────
            doc.setDrawColor(220);
            doc.setLineWidth(0.5);
            doc.line(40, 20, pageW - 40, 20);

            // Application name — right-aligned
            doc.setFontSize(8);
            doc.setFont('helvetica', 'normal');
            doc.setTextColor(120);
            doc.text(appName, pageW - 40, 14, { align: 'right' });

            doc.setTextColor(0);

            // ── Footer ──────────────────────────────────────────────────────
            doc.setDrawColor(220);
            doc.line(40, pageH - 20, pageW - 40, pageH - 20);

            doc.setFontSize(8);
            doc.setFont('helvetica', 'normal');
            doc.setTextColor(120);

            // Source URL — left-aligned
            doc.text(sourceUrl, 40, pageH - 10);

            // Page number — right-aligned
            doc.text(`Page ${pageNum} of ${pageCount}`, pageW - 40, pageH - 10, { align: 'right' });

            doc.setTextColor(0);
        },
    });

    doc.save(`${filename}.pdf`);
}

function csvCell(value) {
    const str = String(value ?? '');
    // Wrap in quotes if the value contains a comma, quote, or newline
    if (str.includes(',') || str.includes('"') || str.includes('\n')) {
        return `"${str.replace(/"/g, '""')}"`;
    }
    return str;
}

function formatPdfCell(value) {
    if (value === null || value === undefined) return '';
    if (typeof value === 'boolean') return value ? 'Yes' : 'No';
    return String(value);
}

function triggerDownload(blob, filename) {
    const url = URL.createObjectURL(blob);
    const a   = document.createElement('a');
    a.href    = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}