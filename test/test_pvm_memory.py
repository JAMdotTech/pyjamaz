import unittest

from pyjamaz.pvm import check_acl, PVMMemoryError
from pyjamaz.pvm.cpython.memory_section import MemorySection
from pyjamaz.pvm.memory import PVMMemory
from pyjamaz.pvm.cpython.interpreter_cpython import PVMInterpreter
from pyjamaz.pvm.constants import PVM_PAGE_SIZE, MEM_R, MEM_W, MEM_RW, MEM_I, ACL_READ_BIT, ACL_WRITE_BIT
from pyjamaz.pvm.memory_section_abstract import set_page_acl, set_range_acl


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
                self.assertTrue(check_acl(section.acl_bitmap, page, 1, ACL_READ_BIT))
                self.assertFalse(check_acl(section.acl_bitmap, page, 1, ACL_WRITE_BIT))

    def test_memory_section_acl_initialization2(self):
        section = MemorySection(address=0, size=65 * PVM_PAGE_SIZE, contents=bytes(65 * PVM_PAGE_SIZE), acl=MEM_R)

        # 65 pages requires 3 bitmap entries (32 pages per entry)
        self.assertEqual(len(section.acl_bitmap), 3)

        # All 65 pages should have read permission
        for page in range(65):
            self.assertTrue(check_acl(section.acl_bitmap, page, 1, ACL_READ_BIT))
            self.assertFalse(check_acl(section.acl_bitmap, page, 1, ACL_WRITE_BIT))

        self.assertFalse(check_acl(section.acl_bitmap, 65, 1, ACL_READ_BIT))

    def test_interpreter_sbrk_updates_acl(self):
        memory = PVMMemory.allocate(rom_pages=1, heap_pages=1, stack_pages=0, arg_pages=0)
        program = DummyProgram(memory)
        vm = PVMInterpreter(program)

        heap_section = memory._heap

        # Initially the single heap page should be writable
        self.assertTrue(check_acl(heap_section.acl_bitmap, 0, 1, ACL_READ_BIT))
        self.assertTrue(check_acl(heap_section.acl_bitmap, 0, 1, ACL_WRITE_BIT))

        set_page_acl(heap_section.acl_bitmap, 0, MEM_R)
        self.assertTrue(check_acl(heap_section.acl_bitmap, 0, 1, ACL_READ_BIT))
        self.assertFalse(check_acl(heap_section.acl_bitmap, 0, 1, ACL_WRITE_BIT))

        # Grow heap by one page (first allocation)
        vm._sbrk(PVM_PAGE_SIZE//2)

        # Existing page remains accessible
        self.assertTrue(check_acl(heap_section.acl_bitmap, 0, 1, ACL_READ_BIT))
        self.assertFalse(check_acl(heap_section.acl_bitmap, 0, 1, ACL_WRITE_BIT))

        # New page should be readable and writable
        self.assertTrue(check_acl(heap_section.acl_bitmap, 1, 1, ACL_READ_BIT))
        self.assertTrue(check_acl(heap_section.acl_bitmap, 1, 1, ACL_WRITE_BIT))

        # Grow heap again to add a new page
        vm._sbrk(PVM_PAGE_SIZE*2)

        # New page should now be accessible
        self.assertTrue(check_acl(heap_section.acl_bitmap, 2, 1, ACL_READ_BIT))
        self.assertTrue(check_acl(heap_section.acl_bitmap, 2, 1, ACL_WRITE_BIT))

        self.assertTrue(check_acl(heap_section.acl_bitmap, 2, 1, ACL_READ_BIT))
        self.assertTrue(check_acl(heap_section.acl_bitmap, 2, 1, ACL_WRITE_BIT))
        set_page_acl(heap_section.acl_bitmap, 2, MEM_I)
        self.assertFalse(check_acl(heap_section.acl_bitmap, 2, 1, ACL_READ_BIT))

        self.assertTrue(check_acl(heap_section.acl_bitmap, 0, 1, ACL_READ_BIT))
        self.assertFalse(check_acl(heap_section.acl_bitmap, 0, 1, ACL_WRITE_BIT))
        set_page_acl(heap_section.acl_bitmap, 0, MEM_I)
        self.assertFalse(check_acl(heap_section.acl_bitmap, 0, 1, ACL_READ_BIT))

        vm._sync_memory()

        # Interpreter metadata should be in sync with the section
        self.assertEqual(heap_section.paged_tail, vm.mem_section_ends[1])
        self.assertEqual(len(heap_section.contents), len(vm.mem_sections[1]))

    def test_bitmap_page_changes(self):
        """Test that setting ACL for one page doesn't affect other pages in the same bitmap."""
        section = MemorySection(
            address=0,
            size=64 * PVM_PAGE_SIZE,  # 64 pages = 2 bitmaps worth
            contents=bytes(64 * PVM_PAGE_SIZE),
            acl=MEM_R
        )

        # All pages should start as readable
        for page in range(64):
            self.assertTrue(check_acl(section.acl_bitmap, page, 1, ACL_READ_BIT))
            self.assertFalse(check_acl(section.acl_bitmap, page, 1, ACL_WRITE_BIT))

        # Set page 5 to writable
        set_page_acl(section.acl_bitmap, 5, MEM_W)

        # Page 5 should now be writable
        self.assertTrue(check_acl(section.acl_bitmap, 5, 1, ACL_READ_BIT))
        self.assertTrue(check_acl(section.acl_bitmap, 5, 1, ACL_WRITE_BIT))

        # Other pages in the same bitmap (0-31) should remain unchanged
        for page in [0, 1, 2, 3, 4, 6, 7, 31]:
            with self.subTest(page=page):
                self.assertTrue(check_acl(section.acl_bitmap, page, 1, ACL_READ_BIT))
                self.assertFalse(check_acl(section.acl_bitmap, page, 1, ACL_WRITE_BIT))

        # Pages in the second bitmap (32-63) should also remain unchanged
        for page in [32, 33, 63]:
            with self.subTest(page=page):
                self.assertTrue(check_acl(section.acl_bitmap, page, 1, ACL_READ_BIT))
                self.assertFalse(check_acl(section.acl_bitmap, page, 1, ACL_WRITE_BIT))


    def test_bitmap_range_changes(self):
        """Test that setting ACL for one page doesn't affect other pages in the same bitmap."""
        nr_pages = 64*4
        section = MemorySection(
            address=0,
            size=nr_pages * PVM_PAGE_SIZE,
            contents=bytes(nr_pages * PVM_PAGE_SIZE),
            acl=MEM_R
        )

        self.assertEqual(len(section.acl_bitmap) , 8)

        # All pages should start as readable
        for page in range(nr_pages):
            self.assertTrue(check_acl(section.acl_bitmap, page, 1, ACL_READ_BIT))
            self.assertFalse(check_acl(section.acl_bitmap, page, 1, ACL_WRITE_BIT))

        #Set page 5 to writable
        set_range_acl(section.acl_bitmap, 5, 2, MEM_W)

        # Page 5 & 6 should now be writable
        self.assertTrue(check_acl(section.acl_bitmap, 5, 2, ACL_READ_BIT))
        self.assertTrue(check_acl(section.acl_bitmap, 5, 2, ACL_WRITE_BIT))

        self.assertFalse(check_acl(section.acl_bitmap, 4, 2, ACL_WRITE_BIT))
        self.assertTrue(check_acl(section.acl_bitmap, 0, 5, ACL_READ_BIT))
        self.assertFalse(check_acl(section.acl_bitmap, 0, 5, ACL_WRITE_BIT))
        self.assertTrue(check_acl(section.acl_bitmap, 5, 1, ACL_WRITE_BIT))
        self.assertTrue(check_acl(section.acl_bitmap, 6, 1, ACL_WRITE_BIT))
        self.assertTrue(check_acl(section.acl_bitmap, 7, nr_pages-7, ACL_READ_BIT))
        self.assertFalse(check_acl(section.acl_bitmap, 7, nr_pages-7, ACL_WRITE_BIT))

    def test_has_inaccessible_acl(self):
        nr_pages = 64 * 4
        memory = PVMMemory.allocate(rom_pages=1, heap_pages=nr_pages, stack_pages=0, arg_pages=0)
        program = DummyProgram(memory)
        vm = PVMInterpreter(program)
        section = memory._heap

        abs_page_nr = section.address//PVM_PAGE_SIZE
        self.assertFalse(memory.has_inaccessible_acl(abs_page_nr, nr_pages))

        set_range_acl(section.acl_bitmap, 7, 4, MEM_I)

        self.assertFalse(memory.has_inaccessible_acl(abs_page_nr, 7))
        self.assertTrue(memory.has_inaccessible_acl(abs_page_nr+7, 1))
        self.assertTrue(memory.has_inaccessible_acl(abs_page_nr+8, 1))
        self.assertTrue(memory.has_inaccessible_acl(abs_page_nr+9, 1))
        self.assertTrue(memory.has_inaccessible_acl(abs_page_nr+10, 1))
        self.assertTrue(memory.has_inaccessible_acl(abs_page_nr+7, 4))
        self.assertFalse(memory.has_inaccessible_acl(abs_page_nr+6, 1))
        self.assertTrue(memory.has_inaccessible_acl(abs_page_nr+6, 2))
        with self.assertRaises(PVMMemoryError):
            set_range_acl(section.acl_bitmap, abs_page_nr+nr_pages, 1, MEM_W)


"""
TODO:
void
zero
write_bytes
read_bytes
is_accessible
"""

if __name__ == "__main__":
    unittest.main()
