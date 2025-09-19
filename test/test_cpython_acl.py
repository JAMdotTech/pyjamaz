import unittest

from pyjamaz.pvm.cpython.memory_section import MemorySection
from pyjamaz.pvm.memory import PVMMemory
from pyjamaz.pvm.cpython.interpreter_cpython import PVMInterpreter
from pyjamaz.pvm.constants import PVM_PAGE_SIZE, MEM_R, MEM_W, MEM_RW, MEM_I, ACL_READ_BIT, ACL_WRITE_BIT


class DummyCode:
    def __init__(self):
        self.code = b"\x00"
        self.jump_table = []
        self.opcode_bitmask = [True]


class DummyProgram:
    def __init__(self, memory):
        self.name = "test_program"
        self.code = DummyCode()
        self.memory = memory
        self.registers = [0] * 13


class TestCPythonACL(unittest.TestCase):

    def test_memory_section_acl_initialization(self):
        section = MemorySection(address=0, size=2 * PVM_PAGE_SIZE, contents=bytes(2 * PVM_PAGE_SIZE), acl=MEM_R)

        self.assertEqual(len(section.acl_bitmap), 1)

        for page in range(2):
            with self.subTest(page=page):
                self.assertTrue(section.check_acl(page, 1, ACL_READ_BIT))
                self.assertFalse(section.check_acl(page, 1, ACL_WRITE_BIT))


    def test_memory_section_acl_initialization2(self):
        section = MemorySection(address=0, size=65 * PVM_PAGE_SIZE, contents=bytes(65 * PVM_PAGE_SIZE), acl=MEM_R)

        # 65 pages requires 3 bitmap entries (32 pages per entry)
        self.assertEqual(len(section.acl_bitmap), 3)

        # All 65 pages should have read permission
        for page in range(65):
            self.assertTrue(section.check_acl(page, 1, ACL_READ_BIT))
            self.assertFalse(section.check_acl(page, 1, ACL_WRITE_BIT))

        self.assertFalse(section.check_acl(65, 1, ACL_READ_BIT))

    def test_interpreter_sbrk_updates_acl(self):
        memory = PVMMemory.allocate(rom_pages=1, heap_pages=1, stack_pages=0, arg_pages=0)

        program = DummyProgram(memory)
        vm = PVMInterpreter(program)

        heap_section = vm.section_objs[1]

        # Initially the single heap page should be writable
        self.assertTrue(heap_section.check_acl(0, 1, ACL_READ_BIT))
        self.assertTrue(heap_section.check_acl(0, 1, ACL_WRITE_BIT))

        heap_section.set_page_acl(0, MEM_R)
        self.assertTrue(heap_section.check_acl(0, 1, ACL_READ_BIT))
        self.assertFalse(heap_section.check_acl(0, 1, ACL_WRITE_BIT))

        # Grow heap by one page (first allocation)
        vm._sbrk(PVM_PAGE_SIZE//2)

        # Existing page remains accessible
        self.assertTrue(heap_section.check_acl(0, 1, ACL_READ_BIT))
        self.assertFalse(heap_section.check_acl(0, 1, ACL_WRITE_BIT))

        # New page should be readable and writable
        self.assertTrue(heap_section.check_acl(1, 1, ACL_READ_BIT))
        self.assertTrue(heap_section.check_acl(1, 1, ACL_WRITE_BIT))

        # Grow heap again to add a new page
        vm._sbrk(PVM_PAGE_SIZE*2)

        # New page should now be accessible
        self.assertTrue(heap_section.check_acl(2, 1, ACL_READ_BIT))
        self.assertTrue(heap_section.check_acl(2, 1, ACL_WRITE_BIT))

        self.assertTrue(heap_section.check_acl(2, 1, ACL_READ_BIT))
        self.assertTrue(heap_section.check_acl(2, 1, ACL_WRITE_BIT))
        heap_section.set_page_acl(2, MEM_I)
        self.assertFalse(heap_section.check_acl(2, 1, ACL_READ_BIT))

        self.assertTrue(heap_section.check_acl(0, 1, ACL_READ_BIT))
        self.assertFalse(heap_section.check_acl(0, 1, ACL_WRITE_BIT))
        heap_section.set_page_acl(0, MEM_I)
        self.assertFalse(heap_section.check_acl(0, 1, ACL_READ_BIT))

        vm._sync_memory()

        # Interpreter metadata should be in sync with the section
        self.assertEqual(heap_section.paged_tail, vm.mem_section_ends[1])
        self.assertEqual(len(heap_section.contents), len(vm.mem_sections[1]))

    def test_bitmap_page_isolation(self):
        """Test that setting ACL for one page doesn't affect other pages in the same bitmap."""
        section = MemorySection(
            address=0,
            size=64 * PVM_PAGE_SIZE,  # 64 pages = 2 bitmaps worth
            contents=bytes(64 * PVM_PAGE_SIZE),
            acl=MEM_R
        )

        # All pages should start as readable
        for page in range(64):
            self.assertTrue(section.check_acl(page, 1, ACL_READ_BIT))
            self.assertFalse(section.check_acl(page, 1, ACL_WRITE_BIT))

        # Set page 5 to writable
        section.set_page_acl(5, MEM_W)

        # Page 5 should now be writable
        self.assertTrue(section.check_acl(5, 1, ACL_READ_BIT))
        self.assertTrue(section.check_acl(5, 1, ACL_WRITE_BIT))

        # Other pages in the same bitmap (0-31) should remain unchanged
        for page in [0, 1, 2, 3, 4, 6, 7, 31]:
            with self.subTest(page=page):
                self.assertTrue(section.check_acl(page, 1, ACL_READ_BIT))
                self.assertFalse(section.check_acl(page, 1, ACL_WRITE_BIT))

        # Pages in the second bitmap (32-63) should also remain unchanged
        for page in [32, 33, 63]:
            with self.subTest(page=page):
                self.assertTrue(section.check_acl(page, 1, ACL_READ_BIT))
                self.assertFalse(section.check_acl(page, 1, ACL_WRITE_BIT))
    #
    # def test_sbrk_preserves_existing_acl(self):
    #     """Test that sbrk operations preserve existing page permissions."""
    #     memory = PVMMemory.allocate(rom_pages=1, heap_pages=2, stack_pages=0, arg_pages=0)
    #     program = DummyProgram(memory)
    #     interp = PVMInterpreter(program)
    #
    #     heap_section = interp.section_objs[1]
    #
    #     # Set custom permissions on the first page
    #     heap_section.set_page_acl(0, MEM_R)  # Make first page read-only
    #
    #     # Verify the first page is now read-only
    #     self.assertTrue(heap_section.check_acl(0, 1, ACL_READ_BIT))
    #     self.assertFalse(heap_section.check_acl(0, 1, ACL_WRITE_BIT))
    #
    #     # Perform sbrk that will add new pages
    #     heap_start = interp.mem_section_starts[1]
    #     current_heap_ptr = heap_start + 2 * PVM_PAGE_SIZE  # Start from end of initial allocation
    #     interp.mem_section_ends[1] = current_heap_ptr
    #
    #     # Grow heap by 2 more pages
    #     result = interp._sbrk(2 * PVM_PAGE_SIZE)
    #     self.assertNotEqual(result, 0)  # Should succeed
    #
    #     # Original page permissions should be preserved
    #     self.assertTrue(heap_section.check_acl(0, 1, ACL_READ_BIT))
    #     self.assertFalse(heap_section.check_acl(0, 1, ACL_WRITE_BIT))
    #
    #     # New pages should be writable (pages 2 and 3)
    #     for page in [2, 3]:
    #         with self.subTest(page=page):
    #             self.assertTrue(heap_section.check_acl(page, 1, ACL_READ_BIT))
    #             self.assertTrue(heap_section.check_acl(page, 1, ACL_WRITE_BIT))
    #
    # def test_bitmap_boundary_handling(self):
    #     """Test ACL operations at bitmap boundaries (32 pages per bitmap)."""
    #     section = MemorySection(
    #         address=0,
    #         size=96 * PVM_PAGE_SIZE,  # 3 bitmaps
    #         contents=bytes(96 * PVM_PAGE_SIZE),
    #         acl=None  # No default ACL
    #     )
    #
    #     # Set different permissions at bitmap boundaries
    #     section.set_page_acl(31, MEM_R)    # Last page of first bitmap
    #     section.set_page_acl(32, MEM_W)    # First page of second bitmap
    #     section.set_page_acl(63, MEM_R)    # Last page of second bitmap
    #     section.set_page_acl(64, MEM_W)    # First page of third bitmap
    #
    #     # Verify permissions
    #     self.assertTrue(section.check_acl(31, 1, ACL_READ_BIT))
    #     self.assertFalse(section.check_acl(31, 1, ACL_WRITE_BIT))
    #
    #     self.assertTrue(section.check_acl(32, 1, ACL_READ_BIT | ACL_WRITE_BIT))
    #     self.assertTrue(section.check_acl(32, 1, ACL_WRITE_BIT))
    #
    #     self.assertTrue(section.check_acl(63, 1, ACL_READ_BIT))
    #     self.assertFalse(section.check_acl(63, 1, ACL_WRITE_BIT))
    #
    #     self.assertTrue(section.check_acl(64, 1, ACL_READ_BIT | ACL_WRITE_BIT))
    #     self.assertTrue(section.check_acl(64, 1, ACL_WRITE_BIT))
    #
    # def test_set_range_acl_across_bitmaps(self):
    #     """Test setting ACL for a range that spans multiple bitmaps."""
    #     section = MemorySection(
    #         address=0,
    #         size=96 * PVM_PAGE_SIZE,
    #         contents=bytes(96 * PVM_PAGE_SIZE),
    #         acl=None
    #     )
    #
    #     # Set a range that spans across bitmap boundaries
    #     section.set_range_acl(30, 5, MEM_W)  # Pages 30-34
    #
    #     # Verify all pages in range have write permissions
    #     for page in range(30, 35):
    #         with self.subTest(page=page):
    #             self.assertTrue(section.check_acl(page, 1, ACL_WRITE_BIT))
    #
    #     # Verify pages outside the range remain unaffected
    #     for page in [29, 35]:
    #         with self.subTest(page=page):
    #             self.assertFalse(section.check_acl(page, 1, ACL_READ_BIT))
    #             self.assertFalse(section.check_acl(page, 1, ACL_WRITE_BIT))
    #
    # def test_check_acl_multi_page(self):
    #     """Test checking ACL for multiple pages at once."""
    #     section = MemorySection(
    #         address=0,
    #         size=10 * PVM_PAGE_SIZE,
    #         contents=bytes(10 * PVM_PAGE_SIZE),
    #         acl=None
    #     )
    #
    #     # Set varying permissions
    #     section.set_page_acl(0, MEM_R)
    #     section.set_page_acl(1, MEM_W)
    #     section.set_page_acl(2, MEM_W)
    #     section.set_page_acl(3, MEM_R)
    #
    #     # Check multi-page ranges
    #     self.assertFalse(section.check_acl(0, 4, ACL_WRITE_BIT))  # Not all pages are writable
    #     self.assertTrue(section.check_acl(1, 2, ACL_WRITE_BIT))   # Pages 1-2 are writable
    #     self.assertTrue(section.check_acl(0, 4, ACL_READ_BIT))    # All pages are readable
    #
    # def test_bitmap_expansion(self):
    #     """Test that bitmap expands correctly when setting ACL for pages beyond current bitmap size."""
    #     section = MemorySection(
    #         address=0,
    #         size=100 * PVM_PAGE_SIZE,  # Large size
    #         contents=bytes(PVM_PAGE_SIZE),  # Small initial content
    #         acl=MEM_R
    #     )
    #
    #     # Initially bitmap should be small
    #     initial_bitmap_size = len(section.acl_bitmap)
    #
    #     # Set ACL for a page far beyond initial bitmap
    #     section.set_page_acl(50, MEM_W)
    #
    #     # Bitmap should have expanded
    #     self.assertGreater(len(section.acl_bitmap), initial_bitmap_size)
    #
    #     # The page should have correct permissions
    #     self.assertTrue(section.check_acl(50, 1, ACL_WRITE_BIT))
    #
    #     # Earlier pages should retain their permissions
    #     self.assertTrue(section.check_acl(0, 1, ACL_READ_BIT))
    #     self.assertFalse(section.check_acl(0, 1, ACL_WRITE_BIT))
    #
    # def test_sbrk_page_alignment(self):
    #     """Test that sbrk correctly handles page-aligned allocations."""
    #     memory = PVMMemory.allocate(rom_pages=1, heap_pages=1, stack_pages=0, arg_pages=0)
    #     program = DummyProgram(memory)
    #     interp = PVMInterpreter(program)
    #
    #     heap_section = interp.section_objs[1]
    #     heap_start = interp.mem_section_starts[1]
    #
    #     # Test various allocation sizes
    #     test_cases = [
    #         (1, "single byte"),
    #         (PVM_PAGE_SIZE - 1, "just under page"),
    #         (PVM_PAGE_SIZE, "exactly one page"),
    #         (PVM_PAGE_SIZE + 1, "just over page"),
    #         (3 * PVM_PAGE_SIZE + 100, "multiple pages plus extra"),
    #     ]
    #
    #     current_ptr = heap_start + PVM_PAGE_SIZE  # Start after initial page
    #     interp.mem_section_ends[1] = current_ptr
    #
    #     for alloc_size, desc in test_cases:
    #         with self.subTest(desc=desc):
    #             old_ptr = current_ptr
    #             new_ptr = interp._sbrk(alloc_size)
    #
    #             self.assertNotEqual(new_ptr, 0, f"Allocation failed for {desc}")
    #             self.assertEqual(new_ptr, old_ptr + alloc_size)
    #
    #             current_ptr = new_ptr
    #
    #             # Verify that all pages up to the new heap end have proper ACL
    #             heap_end_page = (interp.mem_section_ends[1] - heap_start - 1) // PVM_PAGE_SIZE
    #             for page in range(heap_end_page + 1):
    #                 self.assertTrue(
    #                     heap_section.check_acl(page, 1, ACL_READ_BIT | ACL_WRITE_BIT),
    #                     f"Page {page} should be accessible after {desc} allocation"
    #                 )
    #
    # def test_sbrk_page_number_calculation_bug(self):
    #     """Test that sbrk correctly calculates page numbers relative to heap section start."""
    #     memory = PVMMemory.allocate(rom_pages=1, heap_pages=1, stack_pages=0, arg_pages=0)
    #     program = DummyProgram(memory)
    #     interp = PVMInterpreter(program)
    #
    #     heap_section = interp.section_objs[1]
    #     heap_start = interp.mem_section_starts[1]
    #
    #     # The heap doesn't start at address 0, so absolute page numbers will be wrong
    #     # heap_start is typically at 2*PVM_INIT_ZONE_SIZE + rom_size
    #     # This will be a large number, not 0
    #
    #     # Set heap pointer to middle of first page
    #     interp.mem_section_ends[1] = heap_start + PVM_PAGE_SIZE // 2
    #
    #     # Allocate enough to cross into the next page
    #     allocation_size = PVM_PAGE_SIZE  # This should trigger page allocation
    #     result = interp._sbrk(allocation_size)
    #
    #     self.assertNotEqual(result, 0, "Allocation should succeed")
    #
    #     # The critical check: page 0 and page 1 of the heap should be accessible
    #     # If the bug exists (using absolute page numbers), it would set ACL for
    #     # pages far outside the heap section's bitmap
    #     for page in [0, 1]:
    #         with self.subTest(page=page):
    #             has_access = heap_section.check_acl(page, 1, ACL_WRITE_BIT)
    #             self.assertTrue(
    #                 has_access,
    #                 f"Heap page {page} should be writable after sbrk. "
    #                 f"This may indicate sbrk is using absolute page numbers "
    #                 f"instead of section-relative page numbers."
    #             )
    #
    #     # Also check that the bitmap hasn't grown unexpectedly large
    #     # If absolute page numbers were used, the bitmap would need to be huge
    #     bitmap_pages = len(heap_section.acl_bitmap) * 32  # 32 pages per bitmap entry
    #     self.assertLessEqual(
    #         bitmap_pages, 100,
    #         f"Bitmap is unexpectedly large ({bitmap_pages} pages capacity). "
    #         f"This suggests absolute page numbers are being used."
    #     )
    #
    # def test_bitmap_bit_manipulation_correctness(self):
    #     """Test the correctness of bit manipulation in set_page_acl."""
    #     section = MemorySection(
    #         address=0,
    #         size=32 * PVM_PAGE_SIZE,  # One bitmap worth
    #         contents=bytes(32 * PVM_PAGE_SIZE),
    #         acl=None
    #     )
    #
    #     # Test setting individual bits
    #     test_cases = [
    #         (0, MEM_I, "inaccessible"),
    #         (1, MEM_R, "read-only"),
    #         (2, MEM_W, "write-only"),
    #         (3, MEM_RW, "read-write"),
    #     ]
    #
    #     for page, perm, desc in test_cases:
    #         with self.subTest(desc=desc):
    #             section.set_page_acl(page, perm)
    #
    #             if perm == MEM_I:
    #                 self.assertFalse(section.check_acl(page, 1, ACL_READ_BIT))
    #                 self.assertFalse(section.check_acl(page, 1, ACL_WRITE_BIT))
    #             elif perm == MEM_R:
    #                 self.assertTrue(section.check_acl(page, 1, ACL_READ_BIT))
    #                 self.assertFalse(section.check_acl(page, 1, ACL_WRITE_BIT))
    #             elif perm == MEM_W:
    #                 self.assertTrue(section.check_acl(page, 1, ACL_READ_BIT))
    #                 self.assertTrue(section.check_acl(page, 1, ACL_WRITE_BIT))
    #             elif perm == MEM_RW:
    #                 self.assertTrue(section.check_acl(page, 1, ACL_READ_BIT))
    #                 self.assertTrue(section.check_acl(page, 1, ACL_WRITE_BIT))
    #
    #     # Verify that other pages remain unaffected
    #     for page in range(4, 32):
    #         self.assertFalse(section.check_acl(page, 1, ACL_READ_BIT))
    #         self.assertFalse(section.check_acl(page, 1, ACL_WRITE_BIT))
    #
    # def test_acl_page_idx_calculation(self):
    #     """Test that acl_page_idx correctly calculates bit positions."""
    #     from pyjamaz.pvm.memory_section_abstract import acl_page_idx, ACL_PAGES_PER_BITMAP, ACL_BITS_PER_PAGE
    #
    #     # Test bit positions for pages within a single bitmap
    #     # Pages are stored in reverse order within each bitmap
    #     expected_positions = [
    #         (0, 62),   # Page 0 -> bits 62-63 (rightmost page, but at high bit position)
    #         (1, 60),   # Page 1 -> bits 60-61
    #         (2, 58),   # Page 2 -> bits 58-59
    #         (30, 2),   # Page 30 -> bits 2-3
    #         (31, 0),   # Page 31 -> bits 0-1 (leftmost page, at low bit position)
    #     ]
    #
    #     for page, expected_shift in expected_positions:
    #         with self.subTest(page=page):
    #             actual_shift = acl_page_idx(page)
    #             self.assertEqual(
    #                 actual_shift, expected_shift,
    #                 f"Page {page} should have shift {expected_shift}, got {actual_shift}"
    #             )
    #
    # def test_sbrk_does_not_override_other_pages(self):
    #     """Test that sbrk operations don't override ACL bits from other pages."""
    #     memory = PVMMemory.allocate(rom_pages=1, heap_pages=5, stack_pages=0, arg_pages=0)
    #     program = DummyProgram(memory)
    #     interp = PVMInterpreter(program)
    #
    #     heap_section = interp.section_objs[1]
    #     heap_start = interp.mem_section_starts[1]
    #
    #     # Set specific permissions for existing pages
    #     heap_section.set_page_acl(0, MEM_R)   # Page 0: read-only
    #     heap_section.set_page_acl(1, MEM_I)   # Page 1: inaccessible
    #     heap_section.set_page_acl(2, MEM_W)   # Page 2: write-only
    #     heap_section.set_page_acl(3, MEM_RW)  # Page 3: read-write
    #
    #     # Set heap pointer to end of page 3
    #     interp.mem_section_ends[1] = heap_start + 4 * PVM_PAGE_SIZE
    #
    #     # Perform sbrk to allocate page 4
    #     result = interp._sbrk(PVM_PAGE_SIZE)
    #     self.assertNotEqual(result, 0)
    #
    #     # Verify existing pages retain their permissions
    #     test_cases = [
    #         (0, MEM_R, "Page 0 should remain read-only"),
    #         (1, MEM_I, "Page 1 should remain inaccessible"),
    #         (2, MEM_W, "Page 2 should remain write-only"),
    #         (3, MEM_RW, "Page 3 should remain read-write"),
    #     ]
    #
    #     for page, expected_perm, msg in test_cases:
    #         with self.subTest(page=page):
    #             if expected_perm == MEM_I:
    #                 self.assertFalse(heap_section.check_acl(page, 1, ACL_READ_BIT), msg)
    #                 self.assertFalse(heap_section.check_acl(page, 1, ACL_WRITE_BIT), msg)
    #             elif expected_perm == MEM_R:
    #                 self.assertTrue(heap_section.check_acl(page, 1, ACL_READ_BIT), msg)
    #                 self.assertFalse(heap_section.check_acl(page, 1, ACL_WRITE_BIT), msg)
    #             elif expected_perm == MEM_W:
    #                 self.assertTrue(heap_section.check_acl(page, 1, ACL_READ_BIT), msg)
    #                 self.assertTrue(heap_section.check_acl(page, 1, ACL_WRITE_BIT), msg)
    #             elif expected_perm == MEM_RW:
    #                 self.assertTrue(heap_section.check_acl(page, 1, ACL_READ_BIT), msg)
    #                 self.assertTrue(heap_section.check_acl(page, 1, ACL_WRITE_BIT), msg)
    #
    #     # New page should be writable
    #     self.assertTrue(heap_section.check_acl(4, 1, ACL_WRITE_BIT),
    #                    "New page 4 should be writable")
    #
    # def test_sbrk_correct_page_calculation_fixed(self):
    #     """Test the fix for sbrk page number calculation."""
    #     memory = PVMMemory.allocate(rom_pages=1, heap_pages=1, stack_pages=0, arg_pages=0)
    #     program = DummyProgram(memory)
    #     interp = PVMInterpreter(program)
    #
    #     heap_section = interp.section_objs[1]
    #     heap_start = interp.mem_section_starts[1]
    #
    #     # Print diagnostic info
    #     print(f"\nHeap start address: 0x{heap_start:x} ({heap_start})")
    #     print(f"Heap absolute start page: {heap_start // PVM_PAGE_SIZE}")
    #
    #     # The correct calculation should be:
    #     # section_relative_page = (current_heap_ptr - heap_start) // PVM_PAGE_SIZE
    #     # NOT: absolute_page = current_heap_ptr // PVM_PAGE_SIZE
    #
    #     # Test by allocating from the middle of the heap's first page
    #     interp.mem_section_ends[1] = heap_start + 100  # Small offset into first page
    #
    #     # This allocation should add permissions to heap pages 0 and 1
    #     result = interp._sbrk(PVM_PAGE_SIZE)
    #     self.assertNotEqual(result, 0)
    #
    #     # If the bug is present, this will fail because the ACL was set
    #     # for the wrong page numbers
    #     self.assertTrue(
    #         heap_section.check_acl(0, 1, ACL_WRITE_BIT),
    #         "Heap page 0 should be writable"
    #     )
    #     self.assertTrue(
    #         heap_section.check_acl(1, 1, ACL_WRITE_BIT),
    #         "Heap page 1 should be writable"
    #     )


if __name__ == "__main__":
    unittest.main()
