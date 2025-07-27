# Web App for Database Visualization

This project provides a web application using Flask, Docker, and Python to display and visualize data from a PostgreSQL database. It connects directly to the database using pure SQL queries (no ORM) and uses Chart.js for data visualization.

## Features

* Display of `users` table data.
* Display of `loan_requests` table data.
* Visualization of `loan_request_status` distribution using Chart.js.
* Dockerized setup for easy deployment.

## Project Structure
web_app_db_visualizer/
├── app/
│   ├── templates/
│   │   ├── index.html       # Main dashboard with chart
│   │   ├── users.html       # Table for users data
│   │   └── loan_requests.html # Table for loan requests data
│   ├── static/
│   │   ├── css/
│   │   │   └── style.css    # Basic styling
│   │   └── js/
│   │       └── chart_data.js # JavaScript for Chart.js
│   ├── app.py               # Flask application
│   └── database.py          # Database connection and query handling
├── Dockerfile               # Docker build instructions
├── docker-compose.yml       # Docker Compose configuration
├── requirements.txt         # Python dependencies
├── .env                     # Environment variables for database credentials
├── README.md                # This README file


## Setup and Running

### Prerequisites

* Docker and Docker Compose installed on your machine.
* Access to the PostgreSQL database with the provided credentials.

### Steps

1.  **Clone the Repository (or create the files manually):**
    ```bash
    git clone <your-repo-link>
    cd web_app_db_visualizer
    ```

2.  **Create and Configure `.env` file:**
    Create a file named `.env` in the root directory of the project (next to `docker-compose.yml`) and add your PostgreSQL database credentials:

    ```
    DB_HOST='34.9.180.179'
    DB_USER='attoreader'
    DB_PASS='~wgJG^T53_:(dkc[j3'
    DB_NAME='prod-core-atto'
    DB_PORT='5432'
    ```
    **Important:** Replace `~wgJG^T53_:(dkc[j3` with the actual password. Note that special characters in passwords might need to be properly escaped or quoted depending on your shell/environment if you were passing them directly, but `dotenv` usually handles this well.

3.  **Build and Run with Docker Compose:**
    Navigate to the root directory of the project where `docker-compose.yml` is located and run:

    ```bash
    docker-compose up --build
    ```
    This command will:
    * Build the Docker image for your Flask application.
    * Create and start the `web` service.
    * Mount the `app` directory and `.env` file into the container.
    * Expose port 4370 from the container to port 4370 on your host machine.

4.  **Access the Application:**
    Open your web browser and go to:
    ```
    http://localhost:4370
    ```

## Usage

* **Home Page (`/`)**: Provides links to view Users and Loan Requests data, and displays a chart of Loan Request Status distribution.
* **Users Data (`/users`)**: Shows a table of the latest 100 users from the `public.users` table.
* **Loan Requests Data (`/loan_requests`)**: Shows a table of the latest 100 loan requests from the `public.loan_requests` table.
* **API Endpoint (`/api/loan_request_status_data`)**: Returns JSON data for the loan request status visualization.

## Customization

* **Add More Tables**: To display data from other tables (e.g., `loan_summary_statuses`, `answers`), create new Flask routes, new HTML templates, and corresponding SQL queries in `database.py`.
* **More Visualizations**: Extend `app/app.py` to fetch more aggregated data from the database and add new JavaScript code in `app/static/js/chart_data.js` (or new JS files) to create different types of charts using Chart.js.
* **Styling**: Modify `app/static/css/style.css` to change the look and feel of the application.
* **SQL Queries**: The SQL queries are directly written in `app/app.py`. You can modify them to filter, sort, or join data as needed. Be mindful of potential SQL injection if you plan to allow user input for queries (this project does not, for simplicity and security).

## Security Considerations

* **Database Credentials**: Stored in a `.env` file, which is a good practice for development. In production, consider more robust secret management solutions (e.g., Docker Secrets, Kubernetes Secrets, AWS Secrets Manager, HashiCorp Vault).
* **SQL Injection**: Since pure SQL is used, be extremely cautious if you introduce any user-provided input into your SQL queries. Always use parameterized queries (`cursor.execute(query, params)`) to prevent SQL injection. This project already uses parameterized queries where applicable (though the current queries don't take direct user input).
* **Network Security**: Ensure that your PostgreSQL database is accessible from the Docker container. For production, restrict access to only necessary IPs.
* **Error Handling**: Basic error handling is present in `database.py`. For a production application, more comprehensive error logging and user-friendly error pages would be necessary.# atto-analytic
