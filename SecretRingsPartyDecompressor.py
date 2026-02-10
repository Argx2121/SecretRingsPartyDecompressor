import pathlib
from struct import unpack


class Decompress:
    def __init__(self):
        self.root_path = None
        self.folder_path = None
        self.files_to_check = []

    def execute(self):
        current_dir = pathlib.Path(__file__).resolve().parent
        files = [a for a in current_dir.iterdir() if a.is_file() and not a.suffix]
        if not files:
            print("No files without a file extension found, exiting.")
            return

        self.root_path = current_dir / "Decompressed"
        pathlib.Path(self.root_path).mkdir(parents=True, exist_ok=True)

        for file in files:
            self.files_to_check = []
            self.get_packed_files(file)
        print("Files decompressed!")

    def get_nn_name(self, f, start, index):
        f.seek(unpack("<I", f.read(4))[0] + 8)
        block_types = {
            "N_OB": "no", "N_TL": "no",
            "N_NN": "na",
            "N_MA": "nv", "N_MO": "nm", "N_MC": "nd", "N_MT": "ng", "N_MM": "nf", "N_ML": "ni",
            "N_CA": "nd", "N_LI": "ni",
        }
        block = f.read(4).decode("utf-8", "ignore")

        block_type = block[1]
        block = block[:1] + "_" + block[2:]
        block = block_types[block]

        f.seek(start + 20)  # use NOF0 offset
        f.seek(unpack(">I", f.read(4))[0] + start)

        b_name = f.read(4).decode("utf-8", "ignore")
        while b_name != "NEND" and b_name != "NFN0":
            f.seek(unpack("<I", f.read(4))[0], 1)
            b_name = f.read(4).decode("utf-8", "ignore")

        if b_name == "NFN0":
            b_len = unpack("<I", f.read(4))[0]
            end_of_block = b_len + f.tell()
            f.seek(8, 1)

            file_name = f.read(b_len-8).decode("utf-8", "ignore")
            file_name = file_name.replace(chr(0), "")

            f.seek(end_of_block)
            b_name = f.read(4).decode("utf-8", "ignore")
            while b_name != "NEND":
                f.seek(unpack("<I", f.read(4))[0], 1)
                b_name = f.read(4).decode("utf-8", "ignore")
            f.seek(unpack("<I", f.read(4))[0], 1)
        else:
            f.seek(unpack("<I", f.read(4))[0], 1)
            file_name = "Unnamed_File_" + str(index) + "." + block_type.lower() + block
            index += 1
        return file_name

    def get_packed_files(self, file):
        with open(str(file), "rb") as f:
            test = unpack(">I", f.read(4))[0]
            if test != 1:
                print("Invalid file header, skipping " + str(file))
                return
            self.folder_path = self.root_path / file.name
            pathlib.Path(self.folder_path).mkdir(parents=True, exist_ok=True)
            # endian mixing andy
            file_count = unpack("<I", f.read(4))[0]
            dont_care = unpack(">I", f.read(4))[0]
            file_offsets = unpack(">"+str(file_count)+"I", f.read(4*file_count))
            file_ends = list(file_offsets[1:])
            file_ends.append(file.stat().st_size)
            idc = -1
            for off, end in zip(file_offsets, file_ends):
                idc += 1
                f.seek(off)
                if f.read(13).decode("utf-8", "ignore") != "compress v1.0":
                    print("Invalid compression header in " + str(file) + " at offset " + str(off))
                    continue
                if unpack(">3B", f.read(3)) != (0, 64, 0):
                    print("Unrecognised compression header in " + str(file) + " at offset " + str(off))
                    continue
                uncompressed_size = unpack("<I", f.read(4))[0]
                file_size = end - off
                self.decompress(uncompressed_size, file_size, f, idc)
            f.close()

        index = 0

        for file in self.files_to_check:
            with open(str(file), "rb") as f:
                file_name = "Unknown_File_" + str(index)
                start = f.tell()
                magic = f.read(4).decode("utf-8", "ignore")
                if magic == "NGIF":
                    file_name = self.get_nn_name(f, start, index)
                    f.close()
                    pathlib.Path(file).replace(pathlib.Path(pathlib.Path(file).parent, file_name))
                else:  # idk prolly texture
                    # GUYS
                    # SONIC RIDERS MENTION !!!!!!1!
                    f.seek(0)
                    img_count, die = unpack(">2H", f.read(4))
                    if die:
                        f.close()
                        continue
                    texture_offsets = unpack(">"+str(img_count)+"I", f.read(4*img_count))
                    tex_names_len = (texture_offsets[0] - (4 * img_count + 4))
                    f.seek(start + 4 + img_count * 4)
                    texture_names = f.read(tex_names_len).decode("utf-8", "ignore").split(u"\x00")[:img_count]
                    texture_ends = list(texture_offsets[1:0])
                    texture_ends.append(pathlib.Path(file).stat().st_size)

                    for off, end, name in zip(texture_offsets, texture_ends, texture_names):
                        f.seek(off)
                        name = name + ".gvr"
                        fn = open(str(self.folder_path / name), "wb")
                        fn.write(f.read(end - off))
                        fn.close()
                    f.close()
                    pathlib.Path(file).unlink()
                index += 1
                f.close()

    def decompress(self, uncompressed_size, file_size, f, idc):
        buffer_size = 0x1000
        buffer_off = 0xFEE
        working_buffer = [0 for _ in range(buffer_size)]
        file_data = []
        file_name = "newfile" + str(idc)
        while len(file_data) < uncompressed_size:
            control_byte = unpack(">B", f.read(1))[0]
            for i in range(8):
                check_bit = control_byte >> i & 1
                if len(file_data) >= uncompressed_size:
                    break
                if check_bit:
                    new_byte = unpack(">B", f.read(1))[0]
                    file_data.append(new_byte)
                    working_buffer[buffer_off] = new_byte
                    buffer_off = (buffer_off + 1) & 0xFFF
                else:
                    byte1, byte2 = unpack(">2B", f.read(2))
                    buffer_index = byte1 | ((byte2 & 0xf0) << 4)  # fine kitten
                    byte_count = (byte2 >> 0 & 15) + 3

                    for _ in range(byte_count):
                        new_byte = working_buffer[buffer_index]
                        file_data.append(new_byte)
                        working_buffer[buffer_off] = new_byte
                        buffer_off = (buffer_off + 1) & 0xFFF
                        buffer_index = (buffer_index + 1) & 0xFFF

        file_name = "newfile" + str(idc)
        fn = open(str(self.folder_path / file_name), "wb")
        fn.write(bytearray(file_data))
        fn.close()
        self.files_to_check.append(str(self.folder_path / file_name))


if __name__ == '__main__':
    Decompress().execute()



