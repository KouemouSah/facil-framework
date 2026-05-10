"""
USSD Configuration Service

Business logic for USSD configurations including menu validation,
structure analysis, and configuration management
"""

from typing import Optional, List, Dict, Set, Tuple
import asyncpg
from fastapi import HTTPException, status
from loguru import logger

from ..models.ussd import (
    UssdConfigCreate,
    UssdConfigUpdate,
    UssdConfigResponse,
    UssdConfigListResponse,
    UssdOperator,
    MenuNode,
    MenuValidationResult
)
from ..repositories.ussd_repository import UssdRepository


class UssdService:
    """Business logic for USSD configuration operations"""

    def __init__(self):
        self.repository = UssdRepository()

    async def create_config(
        self,
        db: asyncpg.Connection,
        config_data: UssdConfigCreate,
        user_id: int
    ) -> UssdConfigResponse:
        """
        Create new USSD configuration

        Args:
            db: Database connection
            config_data: Configuration data
            user_id: ID of user creating the configuration

        Returns:
            Created configuration

        Raises:
            HTTPException: If validation fails or duplicate exists
        """
        # Validate menu structure
        validation = self._validate_menu_structure(config_data.menu_structure)
        if not validation.is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "message": "Invalid menu structure",
                    "errors": validation.errors
                }
            )

        # Check for duplicate short code
        existing = await self.repository.find_by_short_code(db, config_data.short_code)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Short code {config_data.short_code} is already in use"
            )

        try:
            config = await self.repository.create(db, config_data, user_id)
            logger.info(f"Created USSD config {config.id} for {config.operator_name}")
            return config

        except asyncpg.UniqueViolationError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Configuration with this operator code already exists"
            )

    async def get_config(
        self,
        db: asyncpg.Connection,
        config_id: int
    ) -> UssdConfigResponse:
        """
        Get USSD configuration by ID

        Args:
            db: Database connection
            config_id: Configuration ID

        Returns:
            USSD configuration

        Raises:
            HTTPException: If not found
        """
        config = await self.repository.find_by_id(db, config_id)
        if not config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"USSD configuration {config_id} not found"
            )
        return config

    async def get_config_by_operator(
        self,
        db: asyncpg.Connection,
        operator_name: UssdOperator
    ) -> UssdConfigResponse:
        """
        Get USSD configuration by operator

        Args:
            db: Database connection
            operator_name: Operator name

        Returns:
            USSD configuration

        Raises:
            HTTPException: If not found
        """
        config = await self.repository.find_by_operator(db, operator_name)
        if not config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No configuration found for operator {operator_name.value}"
            )
        return config

    async def list_configs(
        self,
        db: asyncpg.Connection,
        page: int = 1,
        page_size: int = 20,
        is_active: Optional[bool] = None
    ) -> UssdConfigListResponse:
        """
        List USSD configurations with pagination

        Args:
            db: Database connection
            page: Page number (1-indexed)
            page_size: Number of items per page
            is_active: Filter by active status

        Returns:
            Paginated list of configurations
        """
        offset = (page - 1) * page_size
        configs = await self.repository.find_all(db, page_size, offset, is_active)
        total = await self.repository.count(db, is_active)

        return UssdConfigListResponse(
            configs=configs,
            total=total,
            page=page,
            page_size=page_size
        )

    async def update_config(
        self,
        db: asyncpg.Connection,
        config_id: int,
        config_data: UssdConfigUpdate
    ) -> UssdConfigResponse:
        """
        Update USSD configuration

        Args:
            db: Database connection
            config_id: Configuration ID
            config_data: Updated data

        Returns:
            Updated configuration

        Raises:
            HTTPException: If not found or validation fails
        """
        # Check if config exists
        existing = await self.repository.find_by_id(db, config_id)
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"USSD configuration {config_id} not found"
            )

        # Validate menu structure if provided
        if config_data.menu_structure:
            validation = self._validate_menu_structure(config_data.menu_structure)
            if not validation.is_valid:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "message": "Invalid menu structure",
                        "errors": validation.errors
                    }
                )

        # Check for duplicate short code if changing
        if config_data.short_code and config_data.short_code != existing.short_code:
            duplicate = await self.repository.find_by_short_code(db, config_data.short_code)
            if duplicate and duplicate.id != config_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Short code {config_data.short_code} is already in use"
                )

        try:
            config = await self.repository.update(db, config_id, config_data)
            if not config:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"USSD configuration {config_id} not found"
                )

            logger.info(f"Updated USSD config {config_id}")
            return config

        except asyncpg.UniqueViolationError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Duplicate operator code or short code"
            )

    async def delete_config(
        self,
        db: asyncpg.Connection,
        config_id: int
    ) -> None:
        """
        Delete USSD configuration

        Args:
            db: Database connection
            config_id: Configuration ID

        Raises:
            HTTPException: If not found
        """
        deleted = await self.repository.delete(db, config_id)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"USSD configuration {config_id} not found"
            )

        logger.info(f"Deleted USSD config {config_id}")

    async def validate_menu(
        self,
        menu_structure: List[MenuNode]
    ) -> MenuValidationResult:
        """
        Validate menu structure without saving

        Args:
            menu_structure: Menu structure to validate

        Returns:
            Validation result
        """
        return self._validate_menu_structure(menu_structure)

    def _validate_menu_structure(
        self,
        menu_structure: List[MenuNode]
    ) -> MenuValidationResult:
        """
        Validate menu structure for consistency and correctness

        Args:
            menu_structure: Menu structure to validate

        Returns:
            MenuValidationResult with validation details
        """
        errors = []
        warnings = []

        # Get all menu IDs
        menu_ids = {menu.id for menu in menu_structure}
        menu_map = {menu.id: menu for menu in menu_structure}

        # Check for root menu
        root_menus = [menu for menu in menu_structure if menu.is_root]
        if len(root_menus) == 0:
            errors.append("No root menu found")
        elif len(root_menus) > 1:
            errors.append(f"Multiple root menus found: {[m.id for m in root_menus]}")

        # Validate each menu
        for menu in menu_structure:
            # Check for empty options
            if not menu.options:
                errors.append(f"Menu '{menu.id}' has no options")

            # Check option keys are unique
            option_keys = [opt.key for opt in menu.options]
            if len(option_keys) != len(set(option_keys)):
                errors.append(f"Menu '{menu.id}' has duplicate option keys")

            # Validate navigation
            for opt in menu.options:
                if opt.next_menu:
                    if opt.next_menu not in menu_ids:
                        errors.append(
                            f"Menu '{menu.id}' option '{opt.key}' references "
                            f"non-existent menu '{opt.next_menu}'"
                        )
                elif not opt.action:
                    errors.append(
                        f"Menu '{menu.id}' option '{opt.key}' has neither "
                        "next_menu nor action"
                    )

            # Check parent references
            if menu.parent_menu and menu.parent_menu not in menu_ids:
                warnings.append(
                    f"Menu '{menu.id}' references non-existent parent '{menu.parent_menu}'"
                )

        # Check for circular references
        circular = self._detect_circular_references(menu_structure)
        if circular:
            errors.append(f"Circular reference detected: {' -> '.join(circular)}")

        # Check for unreachable menus
        if root_menus:
            reachable = self._find_reachable_menus(root_menus[0], menu_map)
            unreachable = menu_ids - reachable
            if unreachable:
                warnings.append(f"Unreachable menus: {list(unreachable)}")

        # Calculate depth
        max_depth = 0
        if root_menus:
            max_depth = self._calculate_max_depth(root_menus[0], menu_map)

        # Count options
        option_count = sum(len(menu.options) for menu in menu_structure)

        return MenuValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            menu_count=len(menu_structure),
            option_count=option_count,
            max_depth=max_depth
        )

    def _detect_circular_references(
        self,
        menu_structure: List[MenuNode]
    ) -> Optional[List[str]]:
        """
        Detect circular references in menu structure

        Args:
            menu_structure: Menu structure to check

        Returns:
            List of menu IDs in circular path, or None if no circular reference
        """
        menu_map = {menu.id: menu for menu in menu_structure}
        visited = set()
        rec_stack = []

        def visit(menu_id: str) -> Optional[List[str]]:
            if menu_id in rec_stack:
                # Found circular reference
                circular_start = rec_stack.index(menu_id)
                return rec_stack[circular_start:] + [menu_id]

            if menu_id in visited:
                return None

            visited.add(menu_id)
            rec_stack.append(menu_id)

            menu = menu_map.get(menu_id)
            if menu:
                for opt in menu.options:
                    if opt.next_menu:
                        result = visit(opt.next_menu)
                        if result:
                            return result

            rec_stack.pop()
            return None

        for menu in menu_structure:
            if menu.id not in visited:
                result = visit(menu.id)
                if result:
                    return result

        return None

    def _find_reachable_menus(
        self,
        root_menu: MenuNode,
        menu_map: Dict[str, MenuNode]
    ) -> Set[str]:
        """
        Find all menus reachable from root

        Args:
            root_menu: Root menu node
            menu_map: Map of menu ID to menu node

        Returns:
            Set of reachable menu IDs
        """
        reachable = set()
        to_visit = [root_menu.id]

        while to_visit:
            menu_id = to_visit.pop()
            if menu_id in reachable:
                continue

            reachable.add(menu_id)
            menu = menu_map.get(menu_id)

            if menu:
                for opt in menu.options:
                    if opt.next_menu and opt.next_menu not in reachable:
                        to_visit.append(opt.next_menu)

        return reachable

    def _calculate_max_depth(
        self,
        root_menu: MenuNode,
        menu_map: Dict[str, MenuNode],
        visited: Optional[Set[str]] = None
    ) -> int:
        """
        Calculate maximum depth of menu tree

        Args:
            root_menu: Root menu node
            menu_map: Map of menu ID to menu node
            visited: Set of visited menu IDs (for circular reference protection)

        Returns:
            Maximum depth
        """
        if visited is None:
            visited = set()

        if root_menu.id in visited:
            return 0

        visited.add(root_menu.id)
        max_child_depth = 0

        for opt in root_menu.options:
            if opt.next_menu:
                child_menu = menu_map.get(opt.next_menu)
                if child_menu:
                    child_depth = self._calculate_max_depth(child_menu, menu_map, visited.copy())
                    max_child_depth = max(max_child_depth, child_depth)

        return 1 + max_child_depth
