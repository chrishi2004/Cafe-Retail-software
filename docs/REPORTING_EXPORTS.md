# Historical CSV exports

Open Café Reports, Retail Power BI, or the Super Admin Consolidated Dashboard and choose **Historical CSV exports**. Select a report, venture (owner only), branch, and an inclusive range in India Standard Time. Sales can be grouped by day, Monday–Sunday week, or calendar month. The CSV downloads the complete selection, independent of the current page of results. Money is in INR with two decimal places. Timestamps retain their stored value; the separate business-date column identifies the IST date used for filtering.

| Export | How to interpret it |
| --- | --- |
| Sales, Consolidated, Employee summary | Sales use the invoice business date, and exclude drafts, cancellations, voids and returns. Collections use the date of receipt. Refunds use the recorded business date of the actual refund. A partial refund reduces collections by the amount actually returned. The Retail line revenue column compares with the Retail sales report; billed revenue uses invoice totals. |
| Invoice history | Includes full statuses and previously removed invoices when a reversal record survives. Older reversals may lack the original timestamp or invoice fields; missing values remain empty. |
| Payment history | Credit markers and receipts corrected as not received have a zero counted collection. A receipt for a voided sale stays collected until it is refunded or corrected. |
| Refund, cancellation and correction history | Separate records distinguish a reversal, a refund and a correction. Only an actual refund has a nonzero value in the actual refund column. |
| Stock and supplier exports | Stock balances reflect the current snapshot; movements show historical changes. Stock feeds and purchase orders record inventory activity. The supplier payment file uses posted stock-purchase expenses and shows unpaid supplier credit separately. Do not add stock feeds or purchase order totals to recorded supplier cash outflows. |
| Closing history | Uses saved submission and closing snapshots. Counted cash and variance are blank on open or reopened days. |

Group-wide access is owner-only; venture users can export only the company and branches they are authorized to see. Exports do not include authentication fields. New report definitions are listed in [the hosted operational API register](native-operational-openapi.json).
