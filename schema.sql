DROP TABLE IF EXISTS Booking_Segment CASCADE;
DROP TABLE IF EXISTS Booking         CASCADE;
DROP TABLE IF EXISTS Price           CASCADE;
DROP TABLE IF EXISTS Flight          CASCADE;
DROP TABLE IF EXISTS Airline         CASCADE;
DROP TABLE IF EXISTS Card            CASCADE;
DROP TABLE IF EXISTS Billing_Address CASCADE;
DROP TABLE IF EXISTS Customer        CASCADE;
DROP TABLE IF EXISTS Airport         CASCADE;
DROP TABLE IF EXISTS State_Province  CASCADE;


CREATE TABLE State_Province (
    name      VARCHAR(60)  NOT NULL,
    country   VARCHAR(60)  NOT NULL,
    PRIMARY KEY (name, country)
);


CREATE TABLE Airport (
    IATA           CHAR(3)      PRIMARY KEY,
    name           VARCHAR(100) NOT NULL,
    country        VARCHAR(60)  NOT NULL,
    state_name     VARCHAR(60),
    state_country  VARCHAR(60),
    CONSTRAINT iata_upper CHECK (IATA = UPPER(IATA)),
    CONSTRAINT chk_state_for_us_ca CHECK (
        (country NOT IN ('USA', 'Canada'))
        OR (state_name IS NOT NULL AND state_country IS NOT NULL)
    ),
    FOREIGN KEY (state_name, state_country)
        REFERENCES State_Province(name, country)
        ON UPDATE CASCADE
);


CREATE TABLE Airline (
    code     VARCHAR(5)   PRIMARY KEY,
    name     VARCHAR(100) NOT NULL,
    country  VARCHAR(60)  NOT NULL
);


CREATE TABLE Customer (
    cust_id   SERIAL PRIMARY KEY,
    name      TEXT NOT NULL,
    email     TEXT UNIQUE NOT NULL,
    home_iata CHAR(3)
);



CREATE TABLE Billing_Address (
    addr_id     SERIAL       PRIMARY KEY,
    cust_id     INT          NOT NULL,
    name        VARCHAR(100) NOT NULL,
    addr_line1  VARCHAR(150) NOT NULL,
    addr_line2  VARCHAR(150),
    city        VARCHAR(80)  NOT NULL,
    state       VARCHAR(60)  NOT NULL,
    country     VARCHAR(60)  NOT NULL,
    zip         VARCHAR(20)  NOT NULL,
    FOREIGN KEY (cust_id) REFERENCES Customer(cust_id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    UNIQUE (cust_id, name, addr_line1, addr_line2, city, state, country, zip)
);


CREATE TABLE Card (
    card_number   VARCHAR(20)  PRIMARY KEY,
    cust_id       INT          NOT NULL,
    addr_id       INT          NOT NULL,
    name          VARCHAR(100) NOT NULL,
    security_code VARCHAR(4)   NOT NULL,
    exp_date      DATE         NOT NULL,
    FOREIGN KEY (cust_id) REFERENCES Customer(cust_id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    -- ON DELETE RESTRICT enforces "an address can't be deleted while
    -- a card uses it" (spec 4.2).
    FOREIGN KEY (addr_id) REFERENCES Billing_Address(addr_id)
        ON DELETE RESTRICT ON UPDATE CASCADE
);


CREATE TABLE Flight (
    airline_code      VARCHAR(5)  NOT NULL,
    flight_num        VARCHAR(10) NOT NULL,
    flight_date       DATE        NOT NULL,
    origin_iata       CHAR(3)     NOT NULL,
    destination_iata  CHAR(3)     NOT NULL,
    depart_time       TIMESTAMP   NOT NULL,
    arrive_time       TIMESTAMP   NOT NULL,
    max_first         INT         NOT NULL,
    max_eco           INT         NOT NULL,
    PRIMARY KEY (airline_code, flight_num, flight_date),
    FOREIGN KEY (airline_code)     REFERENCES Airline(code) ON UPDATE CASCADE,
    FOREIGN KEY (origin_iata)      REFERENCES Airport(IATA) ON UPDATE CASCADE,
    FOREIGN KEY (destination_iata) REFERENCES Airport(IATA) ON UPDATE CASCADE,
    CONSTRAINT chk_diff_airports CHECK (origin_iata <> destination_iata),
    CONSTRAINT chk_times         CHECK (arrive_time > depart_time),
    CONSTRAINT chk_capacity      CHECK (max_first >= 0 AND max_eco >= 0)
);


CREATE TABLE Price (
    price_id        SERIAL        PRIMARY KEY,
    airline_code    VARCHAR(5)    NOT NULL,
    flight_num      VARCHAR(10)   NOT NULL,
    flight_date     DATE          NOT NULL,
    first_price     NUMERIC(10,2) NOT NULL,
    eco_price       NUMERIC(10,2) NOT NULL,
    effective_from  TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (airline_code, flight_num, flight_date)
        REFERENCES Flight(airline_code, flight_num, flight_date)
        ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT chk_prices_nonneg CHECK (first_price >= 0 AND eco_price >= 0),
    CONSTRAINT chk_first_gt_eco  CHECK (first_price > eco_price),
    UNIQUE (airline_code, flight_num, flight_date, effective_from)
);


CREATE TABLE Booking (
    book_id      SERIAL      PRIMARY KEY,
    cust_id      INT         NOT NULL,
    card_number  VARCHAR(20) NOT NULL,
    booked_at    TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    total_paid   NUMERIC(10,2) NOT NULL,
    FOREIGN KEY (cust_id)     REFERENCES Customer(cust_id) ON UPDATE CASCADE,
    FOREIGN KEY (card_number) REFERENCES Card(card_number) ON UPDATE CASCADE,
    CONSTRAINT chk_total_nonneg CHECK (total_paid >= 0)
);


CREATE TABLE Booking_Segment (
    book_id        INT         NOT NULL,
    seg_num        INT         NOT NULL,
    airline_code   VARCHAR(5)  NOT NULL,
    flight_num     VARCHAR(10) NOT NULL,
    flight_date    DATE        NOT NULL,
    seat           VARCHAR(5)  NOT NULL,
    cabin          VARCHAR(10) NOT NULL,
    fare_paid      NUMERIC(10,2) NOT NULL,
    PRIMARY KEY (book_id, seg_num),
    FOREIGN KEY (book_id) REFERENCES Booking(book_id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    FOREIGN KEY (airline_code, flight_num, flight_date)
        REFERENCES Flight(airline_code, flight_num, flight_date)
        ON UPDATE CASCADE,
    CONSTRAINT chk_cabin CHECK (cabin IN ('first', 'economy')),
    CONSTRAINT chk_fare  CHECK (fare_paid >= 0),
    UNIQUE (airline_code, flight_num, flight_date, seat)
);


CREATE INDEX idx_flight_origin_date  ON Flight(origin_iata, flight_date);
CREATE INDEX idx_flight_dest_date    ON Flight(destination_iata, flight_date);
CREATE INDEX idx_price_flight        ON Price(airline_code, flight_num, flight_date, effective_from DESC);
CREATE INDEX idx_segment_flight      ON Booking_Segment(airline_code, flight_num, flight_date);
CREATE INDEX idx_booking_cust        ON Booking(cust_id);


-- =============================================================
-- Sample data
-- =============================================================

INSERT INTO State_Province (name, country) VALUES
    ('Illinois',   'USA'),
    ('New York',   'USA'),
    ('California', 'USA'),
    ('Ontario',    'Canada');

INSERT INTO Airport (IATA, name, country, state_name, state_country) VALUES
    ('ORD', 'O''Hare International',         'USA',    'Illinois',   'USA'),
    ('JFK', 'John F. Kennedy International', 'USA',    'New York',   'USA'),
    ('LAX', 'Los Angeles International',     'USA',    'California', 'USA'),
    ('YYZ', 'Toronto Pearson International', 'Canada', 'Ontario',    'Canada');

INSERT INTO Airline (code, name, country) VALUES
    ('AA', 'American Airlines', 'USA'),
    ('UA', 'United Airlines',   'USA'),
    ('AC', 'Air Canada',        'Canada');

INSERT INTO Flight (airline_code, flight_num, flight_date,
                    origin_iata, destination_iata,
                    depart_time, arrive_time,
                    max_first, max_eco) VALUES
    ('AA', 'AA100', '2026-05-01', 'ORD', 'JFK',
     '2026-05-01 08:00', '2026-05-01 11:15', 16, 160),
    ('UA', 'UA205', '2026-05-02', 'ORD', 'LAX',
     '2026-05-02 14:30', '2026-05-02 17:00', 20, 180),
    ('AC', 'AC77',  '2026-05-03', 'YYZ', 'ORD',
     '2026-05-03 09:45', '2026-05-03 10:50', 12, 130),
    ('AA', 'AA101', '2026-05-08', 'JFK', 'ORD',
     '2026-05-08 13:00', '2026-05-08 14:30', 16, 160),
    ('AA', 'AA300', '2026-05-01', 'JFK', 'LAX',
     '2026-05-01 14:00', '2026-05-01 17:30', 16, 160);

INSERT INTO Price (airline_code, flight_num, flight_date,
                   first_price, eco_price) VALUES
    ('AA', 'AA100', '2026-05-01',  899.00, 249.00),
    ('UA', 'UA205', '2026-05-02', 1150.00, 310.00),
    ('AC', 'AC77',  '2026-05-03',  620.00, 189.00),
    ('AA', 'AA101', '2026-05-08',  899.00, 249.00),
    ('AA', 'AA300', '2026-05-01', 1050.00, 299.00);

INSERT INTO Customer (name, email, home_iata) VALUES
    ('Jane Austen',      'jausten@example.com', 'ORD'),
    ('Charlotte Bronte', 'cbronte@example.com', 'JFK'),
    ('Alexander Dumas',  'adumas@example.com',  'ORD');

INSERT INTO Billing_Address (cust_id, name, addr_line1, addr_line2,
                             city, state, country, zip) VALUES
    (1, 'Jane Austen',      '123 Michigan Ave', NULL,
     'Chicago', 'Illinois', 'USA', '60601'),
    (2, 'Charlotte Bronte', '456 Broadway',     'Apt 7B',
     'New York', 'New York', 'USA', '10013'),
    (3, 'Alexander Dumas',  '10 W 35th St',     NULL,
     'Chicago', 'Illinois', 'USA', '60616');

INSERT INTO Card (card_number, cust_id, addr_id, name, security_code, exp_date) VALUES
    ('4111111111111111', 1, 1, 'Jane Austen',      '123', '2028-06-30'),
    ('5500000000000004', 2, 2, 'Charlotte Bronte', '456', '2027-11-30'),
    ('340000000000009',  3, 3, 'Alexander Dumas',  '789', '2029-01-31');
