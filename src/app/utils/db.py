from __future__ import annotations

__all__ = ("get_rowcount", "rows_affected")


def get_rowcount(status: str) -> int:
    """Extract the number of rows affected from a PostgreSQL status string.

    PostgreSQL returns a command status string like `'UPDATE 3'` or
    `'DELETE 0'`. This function parses the last part of the string
    to determine how many rows were affected by the query.

    Parameters
    ----------
    status : str
        The command status string returned by PostgreSQL.

    Returns
    -------
    int
        The number of rows affected.
    """
    return int(status.split()[-1])


def rows_affected(status: str) -> bool:
    """Check whether a PostgreSQL query affected any rows.

    Parameters
    ----------
    status : str
        The command status string returned by PostgreSQL.

    Returns
    -------
    bool
        True if the query affected one or more rows, False otherwise.
    """
    return get_rowcount(status) > 0
