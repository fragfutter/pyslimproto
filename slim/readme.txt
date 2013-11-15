Types of data packages

---+ fixed length Client-Server
see Slim/Networking/Slimproto.pm

four-characters commandname
four-bytes package length (of all fields)
field
field
field


HELO, IR  , RESP, BODY...

--+ fixed length Server-Client

two bytes length (that is number of bytes needed for the complete message, including command name)
four characters command
field
field
field
optional a list of http headers

strm, aude, audgm ...



---+ Implementation

---++ message objects
parse(data)
data does contain the command or the length field. Either
strip it or use it to validate the data

serialize()
return byte array with the right length and command field.

---++ Receiving
a Client waits for some bytes to come in (select).
Take first six bytes to determine length and command. Take length bytes and parse them as a message

a Server take first eight bytes to determine command and length Take bytes and parse thema as a message

---++ Sending
call serialize() on the message object and fire away. 




