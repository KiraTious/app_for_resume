-- Base users
INSERT INTO users (username, password, role, created_at, updated_at)
VALUES ('admin', 'admin', 'admin', NOW(), NOW())
ON CONFLICT (username) DO UPDATE SET username = EXCLUDED.username;

INSERT INTO users (username, password, role, created_at, updated_at)
VALUES ('manager', 'admin', 'manager', NOW(), NOW())
ON CONFLICT (username) DO UPDATE SET username = EXCLUDED.username;

INSERT INTO users (username, password, role, created_at, updated_at)
VALUES ('driver1', 'admin', 'driver', NOW(), NOW())
ON CONFLICT (username) DO UPDATE SET username = EXCLUDED.username;

INSERT INTO users (username, password, role, created_at, updated_at)
VALUES ('driver2', 'admin', 'driver', NOW(), NOW())
ON CONFLICT (username) DO UPDATE SET username = EXCLUDED.username;

INSERT INTO users (username, password, role, created_at, updated_at)
VALUES ('driver3', 'admin', 'driver', NOW(), NOW())
ON CONFLICT (username) DO UPDATE SET username = EXCLUDED.username;

-- Drivers linked to driver accounts
DO $$
DECLARE
    driver_user_id INTEGER;
BEGIN
    SELECT id INTO driver_user_id FROM users WHERE username = 'driver1';
    IF driver_user_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM driver WHERE user_id = driver_user_id) THEN
        INSERT INTO driver (first_name, last_name, license_number, user_id, created_at, updated_at)
        VALUES ('Иван', 'Петров', 'LIC-001', driver_user_id, NOW(), NOW());
    END IF;
END $$;

DO $$
DECLARE
    driver_user_id INTEGER;
BEGIN
    SELECT id INTO driver_user_id FROM users WHERE username = 'driver2';
    IF driver_user_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM driver WHERE user_id = driver_user_id) THEN
        INSERT INTO driver (first_name, last_name, license_number, user_id, created_at, updated_at)
        VALUES ('Сергей', 'Ильин', 'LIC-002', driver_user_id, NOW(), NOW());
    END IF;
END $$;

DO $$
DECLARE
    driver_user_id INTEGER;
BEGIN
    SELECT id INTO driver_user_id FROM users WHERE username = 'driver3';
    IF driver_user_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM driver WHERE user_id = driver_user_id) THEN
        INSERT INTO driver (first_name, last_name, license_number, user_id, created_at, updated_at)
        VALUES ('Алексей', 'Сидоров', 'LIC-003', driver_user_id, NOW(), NOW());
    END IF;
END $$;

-- Vehicles assigned to drivers
DO $$
DECLARE
    d1 INTEGER;
    d2 INTEGER;
    d3 INTEGER;
BEGIN
    SELECT id INTO d1 FROM driver WHERE license_number = 'LIC-001';
    SELECT id INTO d2 FROM driver WHERE license_number = 'LIC-002';
    SELECT id INTO d3 FROM driver WHERE license_number = 'LIC-003';

    INSERT INTO vehicle (brand, model, reg_number, driver_id, created_at, updated_at)
    VALUES ('Ford', 'Transit', 'A001AA', d1, NOW(), NOW())
    ON CONFLICT (reg_number) DO NOTHING;

    INSERT INTO vehicle (brand, model, reg_number, driver_id, created_at, updated_at)
    VALUES ('Mercedes', 'Sprinter', 'B002BB', d2, NOW(), NOW())
    ON CONFLICT (reg_number) DO NOTHING;

    INSERT INTO vehicle (brand, model, reg_number, driver_id, created_at, updated_at)
    VALUES ('GAZ', 'Gazelle', 'C003CC', d3, NOW(), NOW())
    ON CONFLICT (reg_number) DO NOTHING;
END $$;

-- Maintenance records
DO $$
DECLARE
    v1 INTEGER;
    v2 INTEGER;
BEGIN
    SELECT id INTO v1 FROM vehicle WHERE reg_number = 'A001AA';
    SELECT id INTO v2 FROM vehicle WHERE reg_number = 'B002BB';

    IF v1 IS NOT NULL AND NOT EXISTS (SELECT 1 FROM maintenance WHERE vehicle_id = v1) THEN
        INSERT INTO maintenance (type_of_work, cost, vehicle_id, created_at, updated_at)
        VALUES ('ТО-1', 15000, v1, NOW(), NOW());
    END IF;

    IF v2 IS NOT NULL AND NOT EXISTS (SELECT 1 FROM maintenance WHERE vehicle_id = v2) THEN
        INSERT INTO maintenance (type_of_work, cost, vehicle_id, created_at, updated_at)
        VALUES ('Замена масла', 5000, v2, NOW(), NOW());
    END IF;
END $$;

-- Sample routes
DO $$
DECLARE
    driver1_id INTEGER;
    driver2_id INTEGER;
    v1 INTEGER;
    v2 INTEGER;
BEGIN
    SELECT id INTO driver1_id FROM driver WHERE license_number = 'LIC-001';
    SELECT id INTO driver2_id FROM driver WHERE license_number = 'LIC-002';
    SELECT id INTO v1 FROM vehicle WHERE reg_number = 'A001AA';
    SELECT id INTO v2 FROM vehicle WHERE reg_number = 'B002BB';

    IF driver1_id IS NOT NULL AND v1 IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM route WHERE driver_id = driver1_id AND vehicle_id = v1
    ) THEN
        INSERT INTO route (start_location, end_location, date, distance, vehicle_id, driver_id, created_at, updated_at)
        VALUES ('Склад', 'Клиент А', CURRENT_DATE, 120.5, v1, driver1_id, NOW(), NOW());
    END IF;

    IF driver2_id IS NOT NULL AND v2 IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM route WHERE driver_id = driver2_id AND vehicle_id = v2
    ) THEN
        INSERT INTO route (start_location, end_location, date, distance, vehicle_id, driver_id, created_at, updated_at)
        VALUES ('Клиент А', 'Склад', CURRENT_DATE + INTERVAL '1 day', 118.0, v2, driver2_id, NOW(), NOW());
    END IF;
END $$;
