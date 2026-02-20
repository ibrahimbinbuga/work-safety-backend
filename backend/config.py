# Configuration for the Work Safety Backend

# Admin Company Codes - These are special codes that don't exist in the companies table
# Users logging in with these codes are treated as admins with access to all companies
ADMIN_COMPANY_CODES = ["ADMIN", "SUPERADMIN", "SYSTEM"]

# Check if a company code belongs to an admin
def is_admin_company_code(company_code: str) -> bool:
    """
    Check if the given company code is an admin company code.
    
    Args:
        company_code: The company code to check
        
    Returns:
        True if the code is an admin code, False otherwise
    """
    return company_code in ADMIN_COMPANY_CODES
