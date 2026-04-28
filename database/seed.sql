-- =============================================================================
-- University Fee Tracking System — Demo Seed Data
-- =============================================================================
-- Run AFTER schema.sql.  Uses INSERT … ON CONFLICT DO NOTHING so it is
-- safe to re-run without creating duplicates.
-- =============================================================================


-- ---------------------------------------------------------------------------
-- Students
-- Batches: 2025–Aug B.Tech CSE | ME | CE
-- Semesters 1–3 for each branch
-- ---------------------------------------------------------------------------
INSERT INTO students (name, roll_number, batch_name, semester) VALUES
  -- CSE Sem 1
  ('Aarav Sharma',    'CSE2501', '2025 – Aug - B.Tech CSE', 'B.Tech CSE – Sem 1'),
  ('Priya Singh',     'CSE2502', '2025 – Aug - B.Tech CSE', 'B.Tech CSE – Sem 1'),
  ('Rohit Gupta',     'CSE2503', '2025 – Aug - B.Tech CSE', 'B.Tech CSE – Sem 1'),
  ('Sneha Patel',     'CSE2504', '2025 – Aug - B.Tech CSE', 'B.Tech CSE – Sem 1'),
  -- CSE Sem 2
  ('Vikram Yadav',    'CSE2505', '2025 – Aug - B.Tech CSE', 'B.Tech CSE – Sem 2'),
  ('Divya Mehta',     'CSE2506', '2025 – Aug - B.Tech CSE', 'B.Tech CSE – Sem 2'),
  ('Aryan Joshi',     'CSE2507', '2025 – Aug - B.Tech CSE', 'B.Tech CSE – Sem 2'),
  -- CSE Sem 3
  ('Kavya Nair',      'CSE2508', '2025 – Aug - B.Tech CSE', 'B.Tech CSE – Sem 3'),
  ('Manish Tiwari',   'CSE2509', '2025 – Aug - B.Tech CSE', 'B.Tech CSE – Sem 3'),

  -- ME Sem 1
  ('Arjun Verma',     'ME2501',  '2025 – Aug - B.Tech ME',  'B.Tech ME – Sem 1'),
  ('Pooja Reddy',     'ME2502',  '2025 – Aug - B.Tech ME',  'B.Tech ME – Sem 1'),
  ('Suresh Pillai',   'ME2503',  '2025 – Aug - B.Tech ME',  'B.Tech ME – Sem 1'),
  -- ME Sem 2
  ('Rahul Kumar',     'ME2504',  '2025 – Aug - B.Tech ME',  'B.Tech ME – Sem 2'),
  ('Ananya Das',      'ME2505',  '2025 – Aug - B.Tech ME',  'B.Tech ME – Sem 2'),
  -- ME Sem 3
  ('Karthik Iyer',    'ME2506',  '2025 – Aug - B.Tech ME',  'B.Tech ME – Sem 3'),
  ('Neha Agarwal',    'ME2507',  '2025 – Aug - B.Tech ME',  'B.Tech ME – Sem 3'),

  -- CE Sem 1
  ('Siddharth Roy',   'CE2501',  '2025 – Aug - B.Tech CE',  'B.Tech CE – Sem 1'),
  ('Anjali Mishra',   'CE2502',  '2025 – Aug - B.Tech CE',  'B.Tech CE – Sem 1'),
  -- CE Sem 2
  ('Vivek Pandey',    'CE2503',  '2025 – Aug - B.Tech CE',  'B.Tech CE – Sem 2'),
  ('Shruti Bose',     'CE2504',  '2025 – Aug - B.Tech CE',  'B.Tech CE – Sem 2'),
  -- CE Sem 3
  ('Nikhil Saxena',   'CE2505',  '2025 – Aug - B.Tech CE',  'B.Tech CE – Sem 3'),
  ('Riya Kapoor',     'CE2506',  '2025 – Aug - B.Tech CE',  'B.Tech CE – Sem 3')
ON CONFLICT (roll_number) DO NOTHING;


-- ---------------------------------------------------------------------------
-- Fees  (March 2026 — partial payments to create Paid/Unpaid mix)
-- ---------------------------------------------------------------------------
INSERT INTO fees (student_id, month, year, amount_paid, payment_date)
SELECT s.student_id, 3, 2026, 15000.00, '2026-03-05'
FROM students s WHERE s.roll_number = 'CSE2501' ON CONFLICT DO NOTHING;

INSERT INTO fees (student_id, month, year, amount_paid, payment_date)
SELECT s.student_id, 3, 2026, 15000.00, '2026-03-07'
FROM students s WHERE s.roll_number = 'CSE2502' ON CONFLICT DO NOTHING;

INSERT INTO fees (student_id, month, year, amount_paid, payment_date)
SELECT s.student_id, 3, 2026, 15000.00, '2026-03-09'
FROM students s WHERE s.roll_number = 'CSE2505' ON CONFLICT DO NOTHING;

INSERT INTO fees (student_id, month, year, amount_paid, payment_date)
SELECT s.student_id, 3, 2026, 15000.00, '2026-03-11'
FROM students s WHERE s.roll_number = 'ME2501' ON CONFLICT DO NOTHING;

INSERT INTO fees (student_id, month, year, amount_paid, payment_date)
SELECT s.student_id, 3, 2026, 15000.00, '2026-03-12'
FROM students s WHERE s.roll_number = 'ME2503' ON CONFLICT DO NOTHING;

INSERT INTO fees (student_id, month, year, amount_paid, payment_date)
SELECT s.student_id, 3, 2026, 15000.00, '2026-03-13'
FROM students s WHERE s.roll_number = 'ME2506' ON CONFLICT DO NOTHING;

INSERT INTO fees (student_id, month, year, amount_paid, payment_date)
SELECT s.student_id, 3, 2026, 15000.00, '2026-03-08'
FROM students s WHERE s.roll_number = 'CE2501' ON CONFLICT DO NOTHING;

INSERT INTO fees (student_id, month, year, amount_paid, payment_date)
SELECT s.student_id, 3, 2026, 15000.00, '2026-03-14'
FROM students s WHERE s.roll_number = 'CE2503' ON CONFLICT DO NOTHING;

INSERT INTO fees (student_id, month, year, amount_paid, payment_date)
SELECT s.student_id, 3, 2026, 15000.00, '2026-03-15'
FROM students s WHERE s.roll_number = 'CE2505' ON CONFLICT DO NOTHING;


-- ---------------------------------------------------------------------------
-- Fees  (April 2026 — fewer paid, more defaulters)
-- ---------------------------------------------------------------------------
INSERT INTO fees (student_id, month, year, amount_paid, payment_date)
SELECT s.student_id, 4, 2026, 15000.00, '2026-04-03'
FROM students s WHERE s.roll_number = 'CSE2501' ON CONFLICT DO NOTHING;

INSERT INTO fees (student_id, month, year, amount_paid, payment_date)
SELECT s.student_id, 4, 2026, 15000.00, '2026-04-06'
FROM students s WHERE s.roll_number = 'CSE2508' ON CONFLICT DO NOTHING;

INSERT INTO fees (student_id, month, year, amount_paid, payment_date)
SELECT s.student_id, 4, 2026, 15000.00, '2026-04-04'
FROM students s WHERE s.roll_number = 'ME2501' ON CONFLICT DO NOTHING;

INSERT INTO fees (student_id, month, year, amount_paid, payment_date)
SELECT s.student_id, 4, 2026, 15000.00, '2026-04-05'
FROM students s WHERE s.roll_number = 'CE2501' ON CONFLICT DO NOTHING;
